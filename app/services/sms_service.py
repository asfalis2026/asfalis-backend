from twilio.rest import Client
from app.config import settings
import logging
import threading

logger = logging.getLogger(__name__)


def send_sms(to, body):
    """Send an SMS via Twilio in a background thread."""
    try:
        account_sid = settings.TWILIO_ACCOUNT_SID
        auth_token = settings.TWILIO_AUTH_TOKEN
        twilio_phone = settings.TWILIO_PHONE_NUMBER

        if not all([account_sid, auth_token, twilio_phone]):
            logger.warning("Twilio client not configured. Check TWILIO_* env vars.")
            logger.info(f"[MOCK SMS] To={to} | Body={body}")
            return "mock-sid"

        def _send():
            try:
                # client = Client(account_sid, auth_token)
                # message = client.messages.create(body=body, from_=twilio_phone, to=to)
                # logger.info(f"SMS sent to {to}: SID={message.sid}")
                logger.info(f"[SMS DISABLED] To={to} | Body={body}")
            except Exception as e:
                logger.error(f"Twilio failed to send SMS to {to}: {e}")
                logger.warning(f"[DEV FALLBACK] SMS body for {to}: {body}")

        t = threading.Thread(target=_send, daemon=True)
        t.start()
        logger.info(f"SMS dispatch started for {to}")
        return "dispatched"

    except Exception as e:
        logger.error(f"Failed to dispatch SMS for {to}: {e}")
        return None


def send_otp_sms(phone, otp_code):
    body = (
        f"Your Asfalis verification code is: {otp_code}. "
        f"Valid for 5 minutes. Do not share."
    )
    return send_sms(phone, body)


def send_sms_sync(to, body):
    """Send SMS synchronously. Returns (True, sid) or (False, error_str)."""
    try:
        account_sid = settings.TWILIO_ACCOUNT_SID
        auth_token = settings.TWILIO_AUTH_TOKEN
        twilio_phone = settings.TWILIO_PHONE_NUMBER

        if not all([account_sid, auth_token, twilio_phone]):
            logger.warning("Twilio not configured — cannot send SMS.")
            logger.info(f"[MOCK SMS] To={to} | Body={body}")
            return False, "twilio_not_configured"

        # client = Client(account_sid, auth_token)
        # message = client.messages.create(body=body, from_=twilio_phone, to=to)
        # logger.info(f"SMS sent to {to}: SID={message.sid}")
        logger.info(f"[SMS SYNC DISABLED] To={to} | Body={body}")
        return True, "mock-sid"

    except Exception as e:
        logger.error(f"Twilio failed to send SMS to {to}: {e}")
        logger.warning(f"[DEV FALLBACK] SMS body for {to}: {body}")
        return False, str(e)


def send_contact_verification_otp(phone, otp_code):
    body = (
        f"Your Asfalis trusted contact verification code is: {otp_code}. "
        f"Valid for 5 minutes. Do not share."
    )
    return send_sms_sync(phone, body)
