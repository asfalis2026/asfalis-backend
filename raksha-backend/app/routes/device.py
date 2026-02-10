
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.device import ConnectedDevice
from app.extensions import db
from marshmallow import Schema, fields, ValidationError
from datetime import datetime
from app.services.sos_service import trigger_sos

device_bp = Blueprint('device', __name__)

class DeviceRegisterSchema(Schema):
    device_name = fields.Str(required=True)
    device_mac = fields.Str(required=True)
    firmware_version = fields.Str(allow_none=True)

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
