
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.services.sos_service import trigger_sos, dispatch_sos, cancel_sos
from app.models.sos_alert import SOSAlert
from app.models.trusted_contact import TrustedContact
from app.models.user import User
from app.utils.timezone_utils import format_datetime_for_response, get_timezone_for_country
from marshmallow import Schema, fields, ValidationError

sos_bp = Blueprint('sos', __name__)


def _serialize_sos_alert(alert, user_country):
    timezone_zone = get_timezone_for_country(user_country).zone if user_country else 'UTC'
    return {
        'alert_id': alert.id,
        'trigger_type': alert.trigger_type,
        'address': alert.address,
        'status': alert.status,
        'triggered_at': format_datetime_for_response(alert.triggered_at, user_country),
        'sent_at': format_datetime_for_response(alert.sent_at, user_country),
        'resolved_at': format_datetime_for_response(alert.resolved_at, user_country),
        'resolution_type': alert.resolution_type,
        'timezone': timezone_zone
    }

class SOSTriggerSchema(Schema):
    latitude = fields.Float(load_default=0.0)
    longitude = fields.Float(load_default=0.0)
    trigger_type = fields.Str(missing='manual')

@sos_bp.route('/trigger', methods=['POST'])
@jwt_required()
def trigger():
    current_user_id = get_jwt_identity()

    # Block SOS if no trusted contacts saved
    contact_count = TrustedContact.query.filter_by(user_id=current_user_id).count()
    if contact_count == 0:
        return jsonify(success=False, error={
            "code": "NO_CONTACTS",
            "message": "You must add at least one emergency contact before sending an SOS."
        }), 400

    schema = SOSTriggerSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify(success=False, error={"code": "VALIDATION_ERROR", "message": "Invalid request", "details": err.messages}), 400

    alert, msg = trigger_sos(current_user_id, data['latitude'], data['longitude'], data['trigger_type'])
    
    if not alert:
         return jsonify(success=False, error={"code": "ERROR", "message": msg}), 400

    user = User.query.get(current_user_id)
    payload = _serialize_sos_alert(alert, user.country if user else None)

    return jsonify(success=True, data=payload, message=msg), 201

@sos_bp.route('/send-now', methods=['POST'])
@jwt_required()
def send_now():
    current_user_id = get_jwt_identity()
    data = request.json
    alert_id = data.get('alert_id')
    
    if not alert_id:
        return jsonify(success=False, error={"code": "VALIDATION_ERROR", "message": "Missing alert_id"}), 400

    success, msg, delivery_report = dispatch_sos(alert_id, current_user_id)
    if not success:
         return jsonify(success=False, error={"code": "ERROR", "message": msg}), 400

    return jsonify(success=True, message=msg, delivery_report=delivery_report), 200

@sos_bp.route('/cancel', methods=['POST'])
@jwt_required()
def cancel():
    current_user_id = get_jwt_identity()
    data = request.json
    alert_id = data.get('alert_id')
    
    if not alert_id:
        return jsonify(success=False, error={"code": "VALIDATION_ERROR", "message": "Missing alert_id"}), 400

    success, msg = cancel_sos(alert_id, current_user_id)
    if not success:
         return jsonify(success=False, error={"code": "ERROR", "message": msg}), 400

    return jsonify(success=True, message=msg), 200


@sos_bp.route('/safe', methods=['POST'])
@jwt_required()
def mark_safe():
    """Mark user as safe and send WhatsApp notifications to all contacts"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    data = request.json
    alert_id = data.get('alert_id')
    
    if not alert_id:
        return jsonify(success=False, error={"code": "VALIDATION_ERROR", "message": "Missing alert_id"}), 400
    
    # Import here to avoid circular imports
    from app.services.sos_service import mark_user_safe
    
    success, msg, contacts_notified = mark_user_safe(alert_id, current_user_id)
    
    if not success:
        # Determine error code from message
        if "not found" in msg.lower():
            error_code = "ALERT_NOT_FOUND"
            status_code = 404
        elif "already resolved" in msg.lower():
            error_code = "ALREADY_RESOLVED"
            status_code = 400
        elif "unauthorized" in msg.lower():
            error_code = "UNAUTHORIZED"
            status_code = 401
        else:
            error_code = "ERROR"
            status_code = 400
        
        return jsonify(success=False, error={"code": error_code, "message": msg}), status_code
    
    # Get the alert to return
    alert = SOSAlert.query.get(alert_id)
    alert_payload = _serialize_sos_alert(alert, user.country if user else None) if alert else None
    response_data = alert_payload or {"alert_id": alert_id, "status": "safe"}
    response_data.update({
        "contacts_notified": contacts_notified,
        "resolution_type": alert.resolution_type if alert else None
    })
    
    return jsonify(
        success=True,
        message=msg,
        data=response_data
    ), 200

@sos_bp.route('/history', methods=['GET'])
@jwt_required()
def history():
    current_user_id = get_jwt_identity()
    alerts = SOSAlert.query.filter_by(user_id=current_user_id).order_by(SOSAlert.triggered_at.desc()).all()
    user = User.query.get(current_user_id)
    payload = [_serialize_sos_alert(alert, user.country if user else None) for alert in alerts]
    return jsonify(success=True, data=payload), 200


@sos_bp.route('/test-whatsapp', methods=['POST'])
@jwt_required()
def test_whatsapp():
    """Dev/debug endpoint — sends a WhatsApp test message synchronously and
    returns the raw Twilio delivery result so you can see exactly what fails.

    Request body::
        { "phone": "+919876543210" }   // E.164 format
    """
    data = request.json or {}
    phone = data.get('phone', '').strip()
    if not phone:
        return jsonify(success=False, error="Missing 'phone' field"), 400

    from app.services.whatsapp_service import send_whatsapp_sync
    from flask import current_app

    result = send_whatsapp_sync(
        phone,
        "🔔 Asfalis WhatsApp test message — if you see this, delivery is working!"
    )

    # Surface Twilio config being used (mask the token)
    debug_config = {
        "TWILIO_ACCOUNT_SID":    current_app.config.get('TWILIO_ACCOUNT_SID', 'NOT SET'),
        "TWILIO_WHATSAPP_FROM":  current_app.config.get('TWILIO_WHATSAPP_FROM', 'NOT SET'),
        "TWILIO_AUTH_TOKEN_SET": bool(current_app.config.get('TWILIO_AUTH_TOKEN')),
    }

    return jsonify(
        success=result["success"],
        delivery=result,
        twilio_config=debug_config
    ), (200 if result["success"] else 502)
