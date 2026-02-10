
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app.models.user import User
from app.extensions import db, limiter
from app.schemas.user_schema import UpdateProfileSchema, FCMTokenSchema
from marshmallow import ValidationError

user_bp = Blueprint('user', __name__)

@user_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify(success=False, error={"code": "NOT_FOUND", "message": "User not found"}), 404

    # Calculate member since string
    member_since = user.created_at.strftime('%B %Y')
    
    # Check protection status (mock/placeholder logic)
    is_protection_active = True 

    return jsonify(success=True, data={
        "user_id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "phone": user.phone,
        "profile_image_url": user.profile_image_url,
        "emergency_contact": user.settings.emergency_number if user.settings else None,
        "member_since": member_since,
        "is_protection_active": is_protection_active,
        "auth_provider": user.auth_provider
    }), 200

@user_bp.route('/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)

    if not user:
        return jsonify(success=False, error={"code": "NOT_FOUND", "message": "User not found"}), 404

    schema = UpdateProfileSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify(success=False, error={"code": "VALIDATION_ERROR", "message": "Invalid request", "details": err.messages}), 400

    if 'full_name' in data:
        user.full_name = data['full_name']
    if 'phone' in data:
        user.phone = data['phone']
    if 'profile_image_url' in data:
        user.profile_image_url = data['profile_image_url']
    
    db.session.commit()

    return jsonify(success=True, message="Profile updated successfully"), 200

@user_bp.route('/fcm-token', methods=['PUT'])
@jwt_required()
def update_fcm_token():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)

    if not user:
        return jsonify(success=False, error={"code": "NOT_FOUND", "message": "User not found"}), 404

    schema = FCMTokenSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify(success=False, error={"code": "VALIDATION_ERROR", "message": "Invalid request", "details": err.messages}), 400

    user.fcm_token = data['fcm_token']
    db.session.commit()

    return jsonify(success=True, message="FCM token updated"), 200

@user_bp.route('/account', methods=['DELETE'])
@jwt_required()
def delete_account():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)

    if not user:
        return jsonify(success=False, error={"code": "NOT_FOUND", "message": "User not found"}), 404

    # Logic to delete related data would go here (cascade delete handles most if configured)
    db.session.delete(user)
    db.session.commit()

    return jsonify(success=True, message="Account deleted successfully"), 200
