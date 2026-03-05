
from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.device import ConnectedDevice
from app.models.sos_alert import SOSAlert
from app.extensions import db
from marshmallow import Schema, fields, ValidationError
from datetime import datetime
from app.services.sos_service import trigger_sos

device_bp = Blueprint('device', __name__)

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class DeviceRegisterSchema(Schema):
    device_name = fields.Str(required=True)
    device_mac = fields.Str(required=True)
    firmware_version = fields.Str(allow_none=True)

class ButtonEventSchema(Schema):
    device_mac = fields.Str(required=True)
    latitude  = fields.Float(load_default=0.0)
    longitude = fields.Float(load_default=0.0)

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@device_bp.route('/register', methods=['POST'])
@jwt_required()
def register_device():
    current_user_id = get_jwt_identity()
    schema = DeviceRegisterSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify(success=False, error={"code": "VALIDATION_ERROR", "message": "Invalid request", "details": err.messages}), 400

    # Check if exists
    device = ConnectedDevice.query.filter_by(device_mac=data['device_mac']).first()
    if device:
        # Update owner if different? Or return conflict?
        # For now, just update ownership and status
        device.user_id = current_user_id
        device.is_connected = True
        device.last_seen = datetime.utcnow()
    else:
        device = ConnectedDevice(
            user_id=current_user_id,
            device_name=data['device_name'],
            device_mac=data['device_mac'],
            firmware_version=data.get('firmware_version'),
            is_connected=True,
            last_seen=datetime.utcnow()
        )
        db.session.add(device)

    db.session.commit()
    return jsonify(success=True, data=device.to_dict()), 201

@device_bp.route('/status', methods=['GET'])
@jwt_required()
def get_device_status():
    current_user_id = get_jwt_identity()
    # Get the most recently paired/seen device
    device = ConnectedDevice.query.filter_by(user_id=current_user_id).order_by(ConnectedDevice.last_seen.desc()).first()
    
    if not device:
        return jsonify(success=False, error={"code": "NOT_FOUND", "message": "No specific device linked"}), 404

    return jsonify(success=True, data=device.to_dict()), 200

@device_bp.route('/<device_id>/status', methods=['PUT'])
@jwt_required()
def update_device_status(device_id):
    current_user_id = get_jwt_identity()
    device = ConnectedDevice.query.filter_by(id=device_id, user_id=current_user_id).first()
    
    if not device:
        return jsonify(success=False, error={"code": "NOT_FOUND", "message": "Device not found"}), 404

    data = request.json
    if 'is_connected' in data:
        device.is_connected = data['is_connected']
        if device.is_connected:
            device.last_seen = datetime.utcnow()

    db.session.commit()
    return jsonify(success=True, data=device.to_dict()), 200


@device_bp.route('/button-event', methods=['POST'])
@jwt_required()
def iot_button_event():
    """
    Called by the phone app whenever it receives an "SOS_TRIGGER_RANDOM_MESSAGE"
    frame from the ESP32 wearable over Bluetooth.

    Single press  → trigger SOS countdown (trigger_type = 'iot_button').
    Double press  → cancel the active SOS countdown / sent alert.
                    Two presses are considered a "double-tap" when they arrive
                    within IOT_DOUBLE_TAP_WINDOW_SECONDS of each other (default 1.5 s).

    Request body:
        {
            "device_mac": "AA:BB:CC:DD:EE:FF",   // required
            "latitude":   12.345,                  // optional, default 0.0
            "longitude":  67.890                   // optional, default 0.0
        }

    Response (trigger):
        { "success": true, "action": "triggered", "message": "...", "data": { <alert> } }

    Response (cancel):
        { "success": true, "action": "cancelled", "message": "..." }
    """
    current_user_id = get_jwt_identity()

    schema = ButtonEventSchema()
    try:
        data = schema.load(request.json or {})
    except ValidationError as err:
        return jsonify(success=False, error={"code": "VALIDATION_ERROR", "message": "Invalid request", "details": err.messages}), 400

    device_mac = data['device_mac']
    latitude   = data['latitude']
    longitude  = data['longitude']

    # --------------------------------------------------------------------- #
    # 1. Verify device belongs to this user
    # --------------------------------------------------------------------- #
    device = ConnectedDevice.query.filter_by(
        device_mac=device_mac, user_id=current_user_id
    ).first()

    if not device:
        return jsonify(success=False, error={
            "code": "NOT_FOUND",
            "message": "Device not found or not paired to your account"
        }), 404

    # --------------------------------------------------------------------- #
    # 2. Double-tap detection
    # --------------------------------------------------------------------- #
    double_tap_window = current_app.config.get('IOT_DOUBLE_TAP_WINDOW_SECONDS', 1.5)
    now = datetime.utcnow()

    is_double_tap = False
    if device.last_button_press_at:
        elapsed = (now - device.last_button_press_at).total_seconds()
        if elapsed <= double_tap_window:
            is_double_tap = True

    # Persist heartbeat regardless of action
    device.last_seen = now
    device.last_button_press_at = now
    device.is_connected = True
    db.session.commit()

    # --------------------------------------------------------------------- #
    # 3a. Double-tap → cancel active SOS
    # --------------------------------------------------------------------- #
    if is_double_tap:
        # Look for the most recent active (countdown or sent) alert
        active_alert = (
            SOSAlert.query
            .filter(
                SOSAlert.user_id == current_user_id,
                SOSAlert.status.in_(['countdown', 'sent'])
            )
            .order_by(SOSAlert.triggered_at.desc())
            .first()
        )

        if not active_alert:
            return jsonify(
                success=True,
                action='cancelled',
                message="Double-tap received but no active SOS found to cancel"
            ), 200

        from app.services.sos_service import cancel_sos
        success, msg = cancel_sos(active_alert.id, current_user_id)

        if not success:
            return jsonify(success=False, error={"code": "ERROR", "message": msg}), 400

        return jsonify(
            success=True,
            action='cancelled',
            message=msg,
            data={'alert_id': active_alert.id}
        ), 200

    # --------------------------------------------------------------------- #
    # 3b. Single press → trigger SOS countdown
    # --------------------------------------------------------------------- #
    from app.models.trusted_contact import TrustedContact
    contact_count = TrustedContact.query.filter_by(user_id=current_user_id).count()
    if contact_count == 0:
        return jsonify(success=False, error={
            "code": "NO_CONTACTS",
            "message": "You must add at least one emergency contact before sending an SOS."
        }), 400

    alert, msg = trigger_sos(
        current_user_id, latitude, longitude, trigger_type='iot_button'
    )

    if not alert:
        return jsonify(success=False, error={"code": "ERROR", "message": msg}), 400

    from app.models.user import User
    from app.utils.timezone_utils import format_datetime_for_response, get_timezone_for_country
    user = User.query.get(current_user_id)
    tz = get_timezone_for_country(user.country).zone if user and user.country else 'UTC'

    return jsonify(
        success=True,
        action='triggered',
        message=msg,
        data={
            'alert_id':     alert.id,
            'trigger_type': alert.trigger_type,
            'status':       alert.status,
            'triggered_at': format_datetime_for_response(alert.triggered_at, user.country if user else None),
            'timezone':     tz
        }
    ), 201


@device_bp.route('/alert', methods=['POST'])
# This might be protected by an API key instead of JWT if coming directly from hardware via gateway
# For now assuming app proxies it or simple protection
def device_alert():
    data = request.json
    mac = data.get('device_mac')
    
    if not mac:
        return jsonify(success=False, error={"code": "VALIDATION_ERROR", "message": "Missing MAC"}), 400

    device = ConnectedDevice.query.filter_by(device_mac=mac).first()
    if not device:
        return jsonify(success=False, error={"code": "NOT_FOUND", "message": "Device not found"}), 404

    # Trigger SOS
    # Need user's last known location
    from app.services.location_service import get_last_location
    
    last_loc = get_last_location(device.user_id)
    lat = last_loc.latitude if last_loc else 0.0
    lng = last_loc.longitude if last_loc else 0.0
    
    alert, msg = trigger_sos(device.user_id, lat, lng, trigger_type='bracelet')
    
    return jsonify(success=True, message=msg), 200

@device_bp.route('/<device_id>', methods=['DELETE'])
@jwt_required()
def delete_device(device_id):
    current_user_id = get_jwt_identity()
    device = ConnectedDevice.query.filter_by(id=device_id, user_id=current_user_id).first()
    
    if not device:
        return jsonify(success=False, error={"code": "NOT_FOUND", "message": "Device not found"}), 404

    db.session.delete(device)
    db.session.commit()
    return jsonify(success=True, message="Device removed"), 200
