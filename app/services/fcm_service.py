
import firebase_admin
from firebase_admin import credentials, messaging
from app.config import Config
from celery import shared_task
import os

# Initialize Firebase App
cred_path = Config.FIREBASE_CREDENTIALS_PATH
if cred_path and os.path.exists(cred_path):
    cred = credentials.Certificate(cred_path)
    try:
        firebase_admin.initialize_app(cred)
    except ValueError:
        # App already initialized
        pass
else:
    print("Warning: Firebase credentials not found. Push notifications will not work.")

@shared_task(ignore_result=True)
def send_push_task(fcm_token, title, body, data):
    """
    Background task to send FCM push notification.
    """
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
    except Exception as e:
        print(f"Error sending message: {e}")

def send_push_notification(fcm_token, title, body, data=None):
    """
    Queue a push notification via FCM.
    """
    if not fcm_token:
        print("Error: No FCM token provided")
        return None

    # Check if firebase is initialized (naive check via cred_path existence)
    # Ideally should check firebase_admin._apps
    if not (Config.FIREBASE_CREDENTIALS_PATH and os.path.exists(Config.FIREBASE_CREDENTIALS_PATH)):
         print("Warning: Firebase not configured, skipping push.")
         return None

    try:
        send_push_task.delay(fcm_token, title, body, data)
        print(f"Push notification task queued for {fcm_token}")
        return "queued"
    except Exception as e:
        print(f"Error queuing message: {e}")
        return None
