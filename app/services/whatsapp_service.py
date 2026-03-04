
from flask import current_app
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
import logging
import threading

logger = logging.getLogger(__name__)

# Twilio error codes relevant to WhatsApp sandbox delivery failures.
# Full list: https://www.twilio.com/docs/api/errors
_SANDBOX_ERRORS = {
    63016: "not_in_sandbox",      # recipient hasn't joined the sandbox
    63032: "not_opted_in",        # recipient needs to send the join keyword
    63015: "account_suspended",   # recipient's WhatsApp account is suspended
    63007: "channel_not_found",   # WhatsApp channel misconfigured on Twilio side
    63001: "channel_auth_failed", # credentials / channel auth issue
    20429: "rate_limited",        # Twilio-side rate limit hit
    21211: "invalid_number",      # malformed E.164 number
    21614: "not_a_mobile_number", # number can't receive messages
}


def send_whatsapp_sync(to_number, message, app_ctx=None):
    """Send a WhatsApp message synchronously and return a delivery report.

    This is the single source of truth for the Twilio API call.  Both the
    fire-and-forget helper and the SOS dispatch path use this function so
    that sandbox/rate-limit errors are always captured and logged.

    Args:
        to_number: Recipient phone number in E.164 format (+91...).
        message:   Body of the WhatsApp message.
        app_ctx:   Flask app object (needed when called from a thread).

    Returns:
        dict with keys:
            success      bool   – True if Twilio accepted the message.
            sid          str    – Twilio message SID (or None on failure).
            status       str    – 'sent' | 'not_in_sandbox' | 'rate_limited' | etc.
            error_code   int    – Raw Twilio error code (None on success).
            error_msg    str    – Human-readable reason (None on success).
    """
    ctx = app_ctx or current_app._get_current_object()
    account_sid = ctx.config.get('TWILIO_ACCOUNT_SID')
    auth_token  = ctx.config.get('TWILIO_AUTH_TOKEN')
    whatsapp_from = ctx.config.get('TWILIO_WHATSAPP_FROM')

    if not all([account_sid, auth_token, whatsapp_from]):
        logger.warning("Twilio WhatsApp credentials not configured, skipping alert.")
        return {"success": False, "sid": None, "status": "not_configured",
                "error_code": None, "error_msg": "Twilio credentials missing"}

    to_wa = to_number if to_number.startswith('whatsapp:') else f'whatsapp:{to_number}'

    try:
        client = Client(account_sid, auth_token)
        msg = client.messages.create(from_=whatsapp_from, body=message, to=to_wa)
        logger.info(f"WhatsApp sent to {to_number}: {msg.sid} (status={msg.status})")
        return {"success": True, "sid": msg.sid, "status": "sent",
                "error_code": None, "error_msg": None}

    except TwilioRestException as e:
        friendly = _SANDBOX_ERRORS.get(e.code, "delivery_failed")
        logger.warning(
            f"WhatsApp to {to_number} failed — Twilio {e.code} [{friendly}]: {e.msg}"
        )
        return {"success": False, "sid": None, "status": friendly,
                "error_code": e.code, "error_msg": e.msg}

    except Exception as e:
        logger.error(f"Unexpected error sending WhatsApp to {to_number}: {e}")
        return {"success": False, "sid": None, "status": "unknown_error",
                "error_code": None, "error_msg": str(e)}


def send_whatsapp_alert(to_number, message):
    """Fire-and-forget WhatsApp alert (non-blocking).  Errors are logged.

    Use send_whatsapp_sync() directly when you need the delivery report
    (e.g. inside dispatch_sos which already runs in the request context).
    """
    try:
        app = current_app._get_current_object()

        def _send():
            with app.app_context():
                send_whatsapp_sync(to_number, message, app_ctx=app)

        t = threading.Thread(target=_send, daemon=True)
        t.start()
        logger.info(f"WhatsApp alert dispatch started for {to_number}")
        return "dispatched"

    except Exception as e:
        logger.error(f"Failed to dispatch WhatsApp alert: {e}")
        return None


def send_safe_notification(user_full_name, contact_phone, safe_time_display: str, timezone_label: str | None = None):
    """
    Send WhatsApp 'I'm Safe' notification to a trusted contact.
    
    Args:
        user_full_name: The name of the user who is safe
        contact_phone: Phone number in E.164 format (e.g., +919876543210)
        safe_time_display: Localized time string (e.g., "Mar 03, 2026 at 08:45 PM")
        timezone_label: Optional timezone abbreviation (e.g., IST)
    
    Returns:
        tuple: (success: bool, message_sid: str or None)
    """
    try:
        account_sid = current_app.config.get('TWILIO_ACCOUNT_SID')
        auth_token = current_app.config.get('TWILIO_AUTH_TOKEN')
        whatsapp_from = current_app.config.get('TWILIO_WHATSAPP_FROM')

        if not all([account_sid, auth_token, whatsapp_from]):
            logger.warning("Twilio WhatsApp credentials not configured")
            return False, None

        # Create the safe message using the localized timestamp
        time_fragment = safe_time_display or "just now"
        if timezone_label:
            time_fragment = f"{time_fragment} {timezone_label}"

        message_body = f"""✅ SAFE: {user_full_name} is now safe!

    They marked themselves safe at {time_fragment}.

    Previous SOS alert has been resolved.

    - Asfalis Safety App"""
        
        # Ensure the 'to' number has the whatsapp: prefix
        if not contact_phone.startswith('whatsapp:'):
            to_number = f'whatsapp:{contact_phone}'
        else:
            to_number = contact_phone
        
        # Send via Twilio
        app = current_app._get_current_object()
        
        def _send():
            with app.app_context():
                try:
                    client = Client(account_sid, auth_token)
                    msg = client.messages.create(
                        from_=whatsapp_from,
                        body=message_body,
                        to=to_number
                    )
                    logger.info(f"Safe notification WhatsApp sent to {contact_phone}: {msg.sid}")
                except Exception as e:
                    logger.error(f"Failed to send safe notification WhatsApp to {contact_phone}: {e}")

        t = threading.Thread(target=_send, daemon=True)
        t.start()
        logger.info(f"Safe notification dispatch started for {contact_phone}")
        return True, "dispatched"
        
    except Exception as e:
        logger.error(f"Failed to send safe notification to {contact_phone}: {e}")
        return False, None

