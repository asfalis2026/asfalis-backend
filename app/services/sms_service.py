
from twilio.rest import Client
from flask import current_app
import logging
import threading

logger = logging.getLogger(__name__)


def _get_twilio_client():
    """Get a Twilio client using current app config."""
    account_sid = current_app.config.get('TWILIO_ACCOUNT_SID')
    auth_token = current_app.config.get('TWILIO_AUTH_TOKEN')
    if not account_sid or not auth_token:
        return None, None, None
    return Client(account_sid, auth_token), account_sid, auth_token


def _send_sms_direct(to, body, from_):
    """Send SMS directly via Twilio using background threads."""
    try:
        account_sid = current_app.config.get('TWILIO_ACCOUNT_SID')
        auth_token = current_app.config.get('TWILIO_AUTH_TOKEN')
        twilio_phone = current_app.config.get('TWILIO_PHONE_NUMBER')

        if not all([account_sid, auth_token, twilio_phone]):
            logger.warning("Twilio credentials not configured, skipping SMS.")
            return

        client = Client(account_sid, auth_token)
        message = client.messages.create(body=body, from_=from_ or twilio_phone, to=to)
        logger.info(f"SMS sent to {to}: {message.sid}")
    except Exception as e:
        logger.error(f"Failed to send SMS to {to}: {e}")


def send_sms(to, body):
    """
    Send an SMS message via Twilio.
    Sends in a background thread to avoid blocking the request,
    without requiring external task queues.
    """
    try:
        account_sid = current_app.config.get('TWILIO_ACCOUNT_SID')
        auth_token = current_app.config.get('TWILIO_AUTH_TOKEN')
        twilio_phone = current_app.config.get('TWILIO_PHONE_NUMBER')

        if not all([account_sid, auth_token, twilio_phone]):
            logger.warning("Twilio client not configured. Check env vars.")
            print(f"--- MOCK SMS TO {to}: {body}")
            return "mock-sid"

        # Use a thread so we don't block the HTTP response
        app = current_app._get_current_object()

        def _send():
            with app.app_context():
                try:
                    client = Client(account_sid, auth_token)
                    message = client.messages.create(body=body, from_=twilio_phone, to=to)
                    logger.info(f"SMS sent to {to}: {message.sid}")
                except Exception as e:
                    logger.error(f"Failed to send SMS to {to}: {e}")

        t = threading.Thread(target=_send, daemon=True)
        t.start()
        logger.info(f"SMS dispatch started for {to}")
        return "dispatched"

    except Exception as e:
        logger.error(f"Failed to dispatch SMS for {to}: {e}")
        return None


def send_otp_sms(phone, otp_code):
    """Send OTP for phone authentication."""
    body = f"Your Asfalis verification code is: {otp_code}. Valid for 5 minutes. Do not share."
    return send_sms(phone, body)


def send_otp_via_verify(phone: str):
    """Send OTP via Twilio Verify service.

    Returns (True, sid) on success, (False, error_str) on failure.
    Falls back to mock-success in dev when credentials are absent.
    """
    account_sid = current_app.config.get('TWILIO_ACCOUNT_SID')
    auth_token = current_app.config.get('TWILIO_AUTH_TOKEN')
    service_sid = current_app.config.get('TWILIO_VERIFY_SERVICE_SID')

    if not all([account_sid, auth_token, service_sid]):
        logger.warning(f"Twilio Verify not configured — skipping OTP send to {phone} (dev mode)")
        return True, "mock"

    try:
        client = Client(account_sid, auth_token)
        verification = client.verify.v2.services(service_sid).verifications.create(
            to=phone, channel='sms'
        )
        logger.info(f"Twilio Verify OTP sent to {phone}: {verification.sid}")
        return True, verification.sid
    except Exception as e:
        logger.error(f"Twilio Verify send failed for {phone}: {e}")
        return False, str(e)


def check_otp_via_verify(phone: str, code: str):
    """Check OTP via Twilio Verify VerificationCheck.

    Returns (True, msg) if approved, (False, msg) otherwise.
    Auto-approves in dev when credentials are absent.
    """
    account_sid = current_app.config.get('TWILIO_ACCOUNT_SID')
    auth_token = current_app.config.get('TWILIO_AUTH_TOKEN')
    service_sid = current_app.config.get('TWILIO_VERIFY_SERVICE_SID')

    if not all([account_sid, auth_token, service_sid]):
        logger.warning(f"Twilio Verify not configured — auto-approving OTP for {phone} (dev mode)")
        return True, "OTP verified (mock)"

    try:
        client = Client(account_sid, auth_token)
        check = client.verify.v2.services(service_sid).verification_checks.create(
            to=phone, code=code
        )
        if check.status == 'approved':
            return True, "OTP verified"
        return False, "Invalid or expired OTP"
    except Exception as e:
        logger.error(f"Twilio Verify check failed for {phone}: {e}")
        return False, str(e)


def send_sos_sms(contact_phone, user_name, message_text, location_url):
    """Send SOS alert SMS to a trusted contact."""
    body = (
        f"🚨 Asfalis EMERGENCY ALERT 🚨\n\n"
        f"{message_text}\n\n"
        f"Sent by: {user_name}\n"
        f"📍 Live Location: {location_url}\n\n"
        f"This is an automated alert from the Asfalis Women Safety app."
    )
    return send_sms(contact_phone, body)
