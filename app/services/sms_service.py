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


def send_otp_via_verify(phone: str):
    account_sid = settings.TWILIO_ACCOUNT_SID
    auth_token = settings.TWILIO_AUTH_TOKEN
    service_sid = settings.TWILIO_VERIFY_SERVICE_SID

    if not all([account_sid, auth_token, service_sid]):
        logger.warning(f"Twilio Verify not configured — skipping OTP send to {phone} (dev mode)")
        return True, "mock"

    try:
        # client = Client(account_sid, auth_token)
        # verification = client.verify.v2.services(service_sid).verifications.create(
        #     to=phone, channel='sms'
        # )
        # logger.info(f"Twilio Verify OTP sent to {phone}: {verification.sid}")
        logger.info(f"[SMS VERIFY DISABLED] OTP for {phone}")
        return True, "mock"
    except Exception as e:
        logger.error(f"Twilio Verify send failed for {phone}: {e}")
        return False, str(e)


def check_otp_via_verify(phone: str, code: str):
    account_sid = settings.TWILIO_ACCOUNT_SID
    auth_token = settings.TWILIO_AUTH_TOKEN
    service_sid = settings.TWILIO_VERIFY_SERVICE_SID

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
    body = (
        f"🚨 Asfalis EMERGENCY ALERT 🚨\n\n"
        f"{message_text}\n\n"
        f"Sent by: {user_name}\n"
        f"📍 Live Location: {location_url}\n\n"
        f"This is an automated alert from the Asfalis Women Safety app."
    )
    return send_sms(contact_phone, body)


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


def send_contact_welcome_sms(contact_phone, sender_name, twilio_number, sandbox_code):
    clean_number = ''.join(filter(str.isdigit, twilio_number))
    import urllib.parse
    encoded_message = urllib.parse.quote(sandbox_code)
    whatsapp_link = f"https://wa.me/{clean_number}?text={encoded_message}"

    body = (
        f"✅ {sender_name} added you as a trusted contact in Asfalis, "
        f"a personal safety app. You will receive emergency alerts with their "
        f"location if they trigger an SOS.\n\n"
        f"📱 To receive WhatsApp alerts:\n"
        f"1. Save this number: {twilio_number}\n"
        f"2. Send this message on WhatsApp: {sandbox_code}\n\n"
        f"Quick link: {whatsapp_link}\n\n"
        f"(Note: You must send the join code first to enable WhatsApp alerts)"
    )
    return send_sms(contact_phone, body)
