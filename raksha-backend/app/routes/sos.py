
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.services.sos_service import trigger_sos, dispatch_sos, cancel_sos
from app.models.sos_alert import SOSAlert
from marshmallow import Schema, fields, ValidationError

sos_bp = Blueprint('sos', __name__)

class SOSTriggerSchema(Schema):
    latitude = fields.Float(required=True)
    longitude = fields.Float(required=True)
    trigger_type = fields.Str(missing='manual')

@sos_bp.route('/trigger', methods=['POST'])
@jwt_required()
def trigger():
    current_user_id = get_jwt_identity()
    schema = SOSTriggerSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify(success=False, error={"code": "VALIDATION_ERROR", "message": "Invalid request", "details": err.messages}), 400

    alert, msg = trigger_sos(current_user_id, data['latitude'], data['longitude'], data['trigger_type'])
    
    if not alert:
         return jsonify(success=False, error={"code": "ERROR", "message": msg}), 400

    return jsonify(success=True, data=alert.to_dict(), message=msg), 201

@sos_bp.route('/send-now', methods=['POST'])
@jwt_required()
def send_now():
    current_user_id = get_jwt_identity() # Check ownership in service if needed
    data = request.json
    alert_id = data.get('alert_id')
    
    if not alert_id:
        return jsonify(success=False, error={"code": "VALIDATION_ERROR", "message": "Missing alert_id"}), 400

    success, msg = dispatch_sos(alert_id)
    if not success:
         return jsonify(success=False, error={"code": "ERROR", "message": msg}), 400

    return jsonify(success=True, message=msg), 200

@sos_bp.route('/cancel', methods=['POST'])
@jwt_required()
def cancel():
    data = request.json
    alert_id = data.get('alert_id')
    
    if not alert_id:
        return jsonify(success=False, error={"code": "VALIDATION_ERROR", "message": "Missing alert_id"}), 400

    success, msg = cancel_sos(alert_id)
    if not success:
         return jsonify(success=False, error={"code": "ERROR", "message": msg}), 400

    return jsonify(success=True, message=msg), 200

@sos_bp.route('/history', methods=['GET'])
@jwt_required()
def history():
    current_user_id = get_jwt_identity()
    alerts = SOSAlert.query.filter_by(user_id=current_user_id).order_by(SOSAlert.triggered_at.desc()).all()
    return jsonify(success=True, data=[a.to_dict() for a in alerts]), 200
