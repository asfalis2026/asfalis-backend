
from flask import request
from flask_socketio import emit, join_room, leave_room
from app.extensions import socketio
from flask_jwt_extended import decode_token
from app.services.location_service import update_location

@socketio.on('connect', namespace='/location')
def connect():
    token = request.args.get('token')
    if not token:
        return False # Reject connection
    
    try:
        decoded = decode_token(token)
        user_id = decoded['sub']
        join_room(f"user_{user_id}") # Room for the user's own devices
        join_room(f"tracking_{user_id}") # Room for their trusted contacts to listen
        emit('status', {'msg': 'Connected to location stream'})
    except Exception as e:
        print(f"Socket connection failed: {e}")
        return False

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
