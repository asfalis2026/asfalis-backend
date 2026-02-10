
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.services.location_service import update_location, get_last_location, start_sharing, stop_sharing
from marshmallow import Schema, fields, ValidationError
import uuid

location_bp = Blueprint('location', __name__)

class LocationUpdateSchema(Schema):
    latitude = fields.Float(required=True)
    longitude = fields.Float(required=True)
    accuracy = fields.Float(allow_none=True)
    is_sharing = fields.Bool(missing=False)

@location_bp.route('/update', methods=['POST'])
@jwt_required()
def update():
    current_user_id = get_jwt_identity()
    schema = LocationUpdateSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify(success=False, error={"code": "VALIDATION_ERROR", "message": "Invalid request", "details": err.messages}), 400

    location = update_location(
        current_user_id, 
        data['latitude'], 
        data['longitude'], 
        data['is_sharing'],
        data.get('accuracy')
    )

    return jsonify(success=True, message="Location updated"), 200

@location_bp.route('/current', methods=['GET'])
@jwt_required()
def get_current():
    current_user_id = get_jwt_identity()
    location = get_last_location(current_user_id)
    
    if not location:
        return jsonify(success=False, error={"code": "NOT_FOUND", "message": "No location history"}), 404

    return jsonify(success=True, data=location.to_dict()), 200

@location_bp.route('/share/start', methods=['POST'])
@jwt_required()
def start_sharing_route():
    current_user_id = get_jwt_identity()
    contacts = start_sharing(current_user_id)
    
    # Generate a dummy tracking URL
    tracking_session_id = str(uuid.uuid4())
    tracking_url = f"https://raksha.app/track/{tracking_session_id}"

    return jsonify(success=True, data={
        "sharing_session_id": tracking_session_id,
        "shared_with": [c.to_dict() for c in contacts],
        "tracking_url": tracking_url
    }), 200

@location_bp.route('/share/stop', methods=['POST'])
@jwt_required()
def stop_sharing_route():
    current_user_id = get_jwt_identity()
    stop_sharing(current_user_id)
    return jsonify(success=True, message="Sharing stopped"), 200
