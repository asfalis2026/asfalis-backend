
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.settings import UserSettings
from app.extensions import db
from app.schemas.settings_schema import SettingsSchema
from marshmallow import ValidationError

settings_bp = Blueprint('settings', __name__)

@settings_bp.route('', methods=['GET'])
@jwt_required()
def get_settings():
    current_user_id = get_jwt_identity()
    settings = UserSettings.query.filter_by(user_id=current_user_id).first()
    
    if not settings:
        return jsonify(success=False, error={"code": "NOT_FOUND", "message": "Settings not found"}), 404

    return jsonify(success=True, data=settings.to_dict()), 200

@settings_bp.route('', methods=['PUT'])
@jwt_required()
def update_settings():
    current_user_id = get_jwt_identity()
    settings = UserSettings.query.filter_by(user_id=current_user_id).first()
    
    if not settings:
        return jsonify(success=False, error={"code": "NOT_FOUND", "message": "Settings not found"}), 404

    schema = SettingsSchema(partial=True)
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify(success=False, error={"code": "VALIDATION_ERROR", "message": "Invalid request", "details": err.messages}), 400

    if 'emergency_number' in data: settings.emergency_number = data['emergency_number']
    if 'sos_message' in data: settings.sos_message = data['sos_message']
    if 'shake_sensitivity' in data: settings.shake_sensitivity = data['shake_sensitivity']
    if 'battery_optimization' in data: settings.battery_optimization = data['battery_optimization']
    if 'haptic_feedback' in data: settings.haptic_feedback = data['haptic_feedback']

    db.session.commit()
    return jsonify(success=True, data=settings.to_dict()), 200
