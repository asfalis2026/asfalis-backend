# Dead Code - Unused SMS/Twilio Verify Functions
# These functions were never called and are kept here for reference only

from twilio.rest import Client
from app.config import settings
import logging
import urllib.parse

logger = logging.getLogger(__name__)


def send_otp_via_verify(phone: str):
    """
    DEPRECATED: Was intended for Twilio Verify API but never implemented.
    Currently using send_otp_sms() instead.
    """
    account_sid = settings.TWILIO_ACCOUNT_SID
    auth_token = settings.TWILIO_AUTH_TOKEN
    service_sid = settings.TWILIO_VERIFY_SERVICE_SID

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
    """
    DEPRECATED: Was intended for Twilio Verify API but never implemented.
    Currently using send_otp_sms() instead.
    """
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
    """
    DEPRECATED: Was intended for SMS-based SOS alerts.
    Currently using WhatsApp messages via whatsapp_service.py instead.
    """
    body = (
        f"🚨 Asfalis EMERGENCY ALERT 🚨\n\n"
        f"{message_text}\n\n"
        f"Sent by: {user_name}\n"
        f"📍 Live Location: {location_url}\n\n"
        f"This is an automated alert from the Asfalis Women Safety app."
    )
    # This would call send_sms() which is disabled
    return None


def send_contact_welcome_sms(contact_phone, sender_name, twilio_number, sandbox_code):
    """
    DEPRECATED: Was intended to send welcome SMS to new contacts.
    Now using in-app sandbox instructions instead to save Twilio credits.
    """
    clean_number = ''.join(filter(str.isdigit, twilio_number))
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
    # This would call send_sms() which is disabled
    return None
