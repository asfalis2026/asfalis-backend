from app.extensions import db, socketio
from app.models.location import LocationHistory
from app.models.user import User
from app.models.trusted_contact import TrustedContact
from datetime import datetime
import asyncio
import logging

logger = logging.getLogger(__name__)


def update_location(user_id, lat, lng, is_sharing=False, accuracy=None):
    new_location = LocationHistory(
        user_id=user_id,
        latitude=lat,
        longitude=lng,
        is_sharing=is_sharing,
        accuracy=accuracy
    )
    db.session.add(new_location)
    db.session.commit()

    if is_sharing:
        user = User.query.get(user_id)
        payload = {
            'user_id': user_id,
            'name': user.full_name if user else 'Unknown',
            'latitude': lat,
            'longitude': lng,
            'accuracy': accuracy,
            'timestamp': datetime.utcnow().isoformat()
        }
        # Emit via python-socketio AsyncServer from sync context
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(
                    socketio.emit(
                        'location_update', payload,
                        room=f"tracking_{user_id}",
                        namespace='/location'
                    )
                )
        except Exception as e:
            logger.warning(f"Socket emit failed (non-critical): {e}")

    return new_location


def get_last_location(user_id):
    return LocationHistory.query.filter_by(user_id=user_id).order_by(LocationHistory.recorded_at.desc()).first()


def start_sharing(user_id):
    last_loc = get_last_location(user_id)
    if last_loc:
        last_loc.is_sharing = True
        db.session.commit()
    contacts = TrustedContact.query.filter_by(user_id=user_id).all()
    return contacts


def stop_sharing(user_id):
    last_loc = get_last_location(user_id)
    if last_loc:
        last_loc.is_sharing = False
        db.session.commit()
    return True
