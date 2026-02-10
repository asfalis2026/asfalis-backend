
from twilio.rest import Client
from app.config import Config

# Initialize Twilio Client
account_sid = Config.TWILIO_ACCOUNT_SID
auth_token = Config.TWILIO_AUTH_TOKEN
twilio_phone = Config.TWILIO_PHONE_NUMBER
client = None

if account_sid and auth_token:
    try:
        client = Client(account_sid, auth_token)
    except Exception as e:
        print(f"Error initializing Twilio client: {e}")

def send_sms(to, body):
    """
    Send an SMS message via Twilio.
    """
    if not client:
        print("Twilio client not initialized. check .env")
        # Fallback to mock for development/testing if keys are missing but code is running
        print(f"--- MOCK SMS TO {to}: {body}")
        return "mock-sid"

    try:
        message = client.messages.create(
            body=body,
            from_=twilio_phone,
            to=to
        )
        print(f"SMS sent to {to}: {message.sid}")
        return message.sid
    except Exception as e:
        print(f"Failed to send SMS to {to}: {e}")
        return None

def send_otp_sms(phone, otp_code):
    """
    Send OTP for phone authentication.
    """
    body = f"Your RAKSHA verification code is: {otp_code}. Valid for 5 minutes. Do not share."
    return send_sms(phone, body)

def send_sos_sms(contact_phone, user_name, message_text, location_url):
    """
    Send SOS alert SMS to a trusted contact.
    """
    body = (
        f"🚨 RAKSHA EMERGENCY ALERT 🚨\n\n"
        f"{message_text}\n\n"
        f"Sent by: {user_name}\n"
        f"📍 Live Location: {location_url}\n\n"
        f"This is an automated alert from the RAKSHA Women Safety app."
    )
    return send_sms(contact_phone, body)
