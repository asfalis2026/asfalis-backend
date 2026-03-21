"""
Socket.IO event handlers for real-time location tracking.

Replaces Flask-SocketIO with python-socketio AsyncServer.
The wire protocol (Socket.IO) is identical — Android client needs no changes.

Namespace: /location

Events:
  connect              — authenticate via token in auth dict or query string
  join_tracking   → trusted contact joins another user's tracking room
  leave_tracking  → leave tracking room
  location_update → push GPS coordinates (stored + broadcast to tracking room)
"""

import logging
from app.extensions import sio

logger = logging.getLogger(__name__)


@sio.event(namespace='/location')
async def connect(sid, environ, auth):
    """Authenticate the connecting client."""
    try:
        from jose import jwt, JWTError
        from app.config import settings

        token = None
        if auth and isinstance(auth, dict):
            token = auth.get('token')
        if not token:
            # Try query string (e.g. ?token=xyz)
            query = environ.get('QUERY_STRING', '')
            for part in query.split('&'):
                if part.startswith('token='):
                    token = part.split('=', 1)[1]
                    break

        if not token:
            logger.warning(f"Socket connect rejected (no token): {sid}")
            return False  # reject

        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get('sub')
        if not user_id:
            return False

        await sio.save_session(sid, {'user_id': user_id}, namespace='/location')
        await sio.enter_room(sid, f"user_{user_id}", namespace='/location')
        logger.info(f"Socket connected: {sid} (user={user_id})")

    except Exception as e:
        logger.warning(f"Socket auth failed for {sid}: {e}")
        return False


@sio.event(namespace='/location')
async def disconnect(sid):
    logger.info(f"Socket disconnected: {sid}")


@sio.event(namespace='/location')
async def join_tracking(sid, data):
    """Trusted contact joins a user's tracking room."""
    session = await sio.get_session(sid, namespace='/location')
    viewer_id = session.get('user_id')
    tracked_user_id = data.get('user_id')

    if not tracked_user_id:
        await sio.emit('error', {'message': 'user_id required'}, to=sid, namespace='/location')
        return

    room = f"tracking_{tracked_user_id}"
    await sio.enter_room(sid, room, namespace='/location')
    logger.info(f"User {viewer_id} joined tracking room for {tracked_user_id}")
    await sio.emit('tracking_joined', {'room': room}, to=sid, namespace='/location')


@sio.event(namespace='/location')
async def leave_tracking(sid, data):
    """Leave a tracking room."""
    tracked_user_id = data.get('user_id')
    if tracked_user_id:
        room = f"tracking_{tracked_user_id}"
        await sio.leave_room(sid, room, namespace='/location')
        logger.info(f"Socket {sid} left tracking room {room}")


@sio.event(namespace='/location')
async def location_update(sid, data):
    """Receive a GPS update and broadcast it to watchers."""
    session = await sio.get_session(sid, namespace='/location')
    user_id = session.get('user_id')
    if not user_id:
        return

    lat = data.get('latitude')
    lng = data.get('longitude')
    accuracy = data.get('accuracy')
    is_sharing = data.get('is_sharing', False)

    if lat is None or lng is None:
        return

    try:
        from app.services.location_service import update_location
        from app.database import ScopedSession
        update_location(user_id, lat, lng, is_sharing, accuracy)
        ScopedSession.remove()
    except Exception as e:
        logger.error(f"Failed to save location from socket: {e}")
