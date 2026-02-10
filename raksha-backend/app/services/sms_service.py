
from app.config import Config

def send_sms(to, body):
    """
    Send SMS via Twilio (Mock implementation for now).
    """
    print(f"--- SMS SENT TO {to} ---")
    print(body)
    print("------------------------")
    return "mock-sid"
