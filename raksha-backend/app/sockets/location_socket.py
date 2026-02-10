
from flask import request
from flask_socketio import emit, join_room, leave_room
from app.extensions import socketio, db # Added db import
from flask_jwt_extended import decode_token
from app.services.location_service import update_location
from app.models.trusted_contact import TrustedContact # Added model import
from app.models.user import User # Added model import

@socketio.on('connect', namespace='/location')
def connect():
    token = request.args.get('token')
    if not token:
        return False # Reject connection
    
    try:
        decoded = decode_token(token)
        user_id = decoded['sub']
        # Join own room for self-updates or device updates
        join_room(f"user_{user_id}") 
        emit('status', {'msg': 'Connected to location stream'})
    except Exception as e:
        print(f"Socket connection failed: {e}")
        return False

@socketio.on('join_tracking', namespace='/location')
def handle_join_tracking(data):
    """
    Allow a trusted contact to join the tracking room of a user.
    data = { 'target_user_id': 'uuid' }
    """
    token = request.args.get('token') # Or passed in data
    if not token:
        # Try getting from data if not in query params (client variation)
        token = data.get('token')
        
    if not token or 'target_user_id' not in data:
        emit('error', {'msg': 'Missing token or target_user_id'})
        return

    try:
        decoded = decode_token(token)
        requester_id = decoded['sub']
        target_user_id = data['target_user_id']

        # 1. Check if requester is authorized (is a trusted contact or the user themselves)
        if requester_id == target_user_id:
            join_room(f"tracking_{target_user_id}")
            emit('joined', {'room': f"tracking_{target_user_id}", 'msg': 'Joined own tracking room'})
            return

        # Check trusted contact relationship
        # Logic: Does target_user have requester_user in their contacts?
        # NOTE: The current TrustedContact model likely stores contacts by phone/email, 
        # not necessarily linking to a User ID directly if they aren't registered.
        # But if they are using the app (websocket), they must be a registered User.
        # We need to find if target_user has a contact record that matches requester's phone/email.
        
        requester = User.query.get(requester_id)
        if not requester:
             emit('error', {'msg': 'Requester user not found'})
             return

        # Find if target user has listed this requester as a contact
        # This assumes TrustedContact has phone field we can match against requester.phone
        contact_record = TrustedContact.query.filter_by(
            user_id=target_user_id,
            phone=requester.phone
        ).first()

        if contact_record:
            join_room(f"tracking_{target_user_id}")
            emit('joined', {'room': f"tracking_{target_user_id}", 'msg': f"Tracking user {target_user_id}"})
        else:
            emit('error', {'msg': 'Unauthorized: You are not a trusted contact'})

    except Exception as e:
        print(f"Join tracking failed: {e}")
        emit('error', {'msg': str(e)})

@socketio.on('leave_tracking', namespace='/location')
def handle_leave_tracking(data):
    target_user_id = data.get('target_user_id')
    if target_user_id:
        leave_room(f"tracking_{target_user_id}")
        emit('left', {'room': f"tracking_{target_user_id}"})

@socketio.on('location_update', namespace='/location')
def handle_location_update(data):
    # expect data = { token, latitude, longitude, accuracy, is_sharing }
    token = data.get('token')
    if not token:
        return

    try:
        decoded = decode_token(token)
        user_id = decoded['sub']
        
        # update location service
        update_location(
            user_id,
            data['latitude'],
            data['longitude'],
            data.get('is_sharing', False),
            data.get('accuracy')
        )
    except Exception as e:
        print(f"Location update failed: {e}")
