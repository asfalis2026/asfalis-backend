
from app.config import Config

def send_push_notification(fcm_token, title, body, data=None):
    """
    Send push notification via FCM (Mock implementation).
    """
    print(f"--- PUSH SENT TO {fcm_token} ---")
    print(f"Title: {title}")
    print(f"Body: {body}")
    print(f"Data: {data}")
    print("--------------------------------")
    return "mock-message-id"
