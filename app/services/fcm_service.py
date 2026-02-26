
import firebase_admin
from firebase_admin import credentials, messaging
from app.config import Config
import os
import json
import logging
import threading

logger = logging.getLogger(__name__)

# Initialize Firebase App
cred_path = Config.FIREBASE_CREDENTIALS_PATH
cred_json = Config.FIREBASE_CREDENTIALS_JSON

try:
    if cred_path and os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
    elif cred_json:
        cred = credentials.Certificate(json.loads(cred_json))
        firebase_admin.initialize_app(cred)
    else:
        logger.warning("Firebase credentials not found (PATH or JSON). Push notifications will not work.")
except ValueError:
    # App already initialized
    pass
except Exception as e:
    logger.error(f"Error initializing Firebase: {e}")


def _is_firebase_ready():
    """Check if Firebase is initialized."""
    return bool(firebase_admin._apps)


def send_push_notification(fcm_token, title, body, data=None):
    """
    Send a push notification via FCM in a background thread.
    No external task queue required.
    """
    if not fcm_token:
        logger.error("No FCM token provided")
        return None

    if not _is_firebase_ready():
        logger.warning("Firebase not configured, skipping push notification.")
        return None

    def _send():
        try:
            message = messaging.Message(
                notification=messaging.Notification(title=title, body=body),
                data=data or {},
                token=fcm_token,
                android=messaging.AndroidConfig(
                    priority='high',
                    notification=messaging.AndroidNotification(
                        channel_id='sos_channel',
                        priority='max',
                        sound='alarm'
                    )
                )
            )
            response = messaging.send(message)
            logger.info(f"Push notification sent: {response}")
        except Exception as e:
            logger.error(f"Error sending push notification: {e}")

    t = threading.Thread(target=_send, daemon=True)
    t.start()
    logger.info(f"Push notification dispatch started for token: {fcm_token[:20]}...")
    return "dispatched"
