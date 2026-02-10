
import firebase_admin
from firebase_admin import credentials, messaging
from app.config import Config
import os

# Initialize Firebase App
cred_path = Config.FIREBASE_CREDENTIALS_PATH
if os.path.exists(cred_path):
    cred = credentials.Certificate(cred_path)
    try:
        firebase_admin.initialize_app(cred)
    except ValueError:
        # App already initialized
        pass
else:
    print(f"WARNING: Firebase credentials not found at {cred_path}")

def send_push_notification(fcm_token, title, body, data=None):
    """
    Send push notification via FCM.
    """
    if not fcm_token:
        print("Error: No FCM token provided")
        return None

    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
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
        print(f"Successfully sent message: {response}")
        return response
    except Exception as e:
        print(f"Error sending message: {e}")
        return None
