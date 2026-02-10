
from app.extensions import db
from app.models.location import LocationHistory
from app.models.user import User
from app.models.trusted_contact import TrustedContact
from datetime import datetime
from app.extensions import socketio

def update_location(user_id, lat, lng, is_sharing=False, accuracy=None):
    # Save to history
    # In production, we might want to sample this instead of saving every single point
    new_location = LocationHistory(
        user_id=user_id,
        latitude=lat,
        longitude=lng,
        is_sharing=is_sharing,
        accuracy=accuracy
    )
    db.session.add(new_location)
    db.session.commit()

    # If sharing, broadcast via WebSocket
    if is_sharing:
        user = User.query.get(user_id)
        # Emit to a room specific to this user's trusted contacts
        # For now, just broadcasting to a user-specific room
        socketio.emit('location_update', {
            'user_id': user_id,
            'name': user.full_name,
            'latitude': lat,
            'longitude': lng,
            'accuracy': accuracy,
            'timestamp': datetime.utcnow().isoformat()
        }, room=f"tracking_{user_id}")
    
    return new_location

def get_last_location(user_id):
    return LocationHistory.query.filter_by(user_id=user_id).order_by(LocationHistory.recorded_at.desc()).first()

def start_sharing(user_id):
    # Logic to notify contacts that sharing started
    user = User.query.get(user_id)
    # Update latest location to sharing=True
    last_loc = get_last_location(user_id)
    if last_loc:
        last_loc.is_sharing = True
        db.session.commit()
    
    # Return contacts being shared with
    contacts = TrustedContact.query.filter_by(user_id=user_id).all()
    return contacts

def stop_sharing(user_id):
    last_loc = get_last_location(user_id)
    if last_loc:
        last_loc.is_sharing = False
        db.session.commit()
    return True
