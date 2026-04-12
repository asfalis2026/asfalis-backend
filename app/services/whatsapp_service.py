# whatsapp_service.py — no Flask dependencies; JWT handling lives in app/routes/auth.py
from app.config import settings
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
import logging
import threading

logger = logging.getLogger(__name__)

_SANDBOX_ERRORS = {
    63016: "not_in_sandbox",
    63032: "not_opted_in",
    63015: "account_suspended",
    63007: "channel_not_found",
    63001: "channel_auth_failed",
    20429: "rate_limited",
    21211: "invalid_number",
    21614: "not_a_mobile_number",
}

TRIGGER_TYPE_LABELS = {
    "manual":    "🔴 Manual SOS (user pressed the SOS button)",
    "iot_button": "📣 Wearable Button SOS (IoT device triggered)",
    "auto_fall":  "⚠️ Auto-SOS (fall detected by accelerometer)",
    "auto_shake": "⚠️ Auto-SOS (unusual motion detected)",
    "auto":       "⚠️ Auto-SOS (unusual activity detected)",
    "bracelet":   "🔴 Bracelet SOS",
}


def _build_sos_body(user_name, trigger_type, trigger_reason, maps_link):
    label = TRIGGER_TYPE_LABELS.get(trigger_type, f"SOS ({trigger_type})")
    lines = [
        "🚨 *EMERGENCY ALERT* 🚨",
        "",
        f"*{user_name}* needs help!",
        "",
        f"*Trigger:* {label}",
    ]
    if trigger_reason:
        lines.append(f"*Reason:* {trigger_reason}")
    if maps_link:
        lines += ["", f"📍 *Location:* {maps_link}"]
    else:
        lines += ["", "📍 *Location:* Not available"]
    lines += ["", "Please check on them immediately.", "— Asfalis Safety App"]
    return "\n".join(lines)


def send_whatsapp_sync(to_number, message, app_ctx=None):
    """Send a WhatsApp message synchronously and return a delivery report."""
    account_sid = settings.TWILIO_WA_ACCOUNT_SID or settings.TWILIO_ACCOUNT_SID
    auth_token  = settings.TWILIO_WA_AUTH_TOKEN  or settings.TWILIO_AUTH_TOKEN
    whatsapp_from = settings.TWILIO_WHATSAPP_FROM

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
        logger.warning(f"WhatsApp to {to_number} failed — Twilio {e.code} [{friendly}]: {e.msg}")
        return {"success": False, "sid": None, "status": friendly,
                "error_code": e.code, "error_msg": e.msg}

    except Exception as e:
        logger.error(f"Unexpected error sending WhatsApp to {to_number}: {e}")
        return {"success": False, "sid": None, "status": "unknown_error",
                "error_code": None, "error_msg": str(e)}


def send_whatsapp_alert(to_number, message):
    """Fire-and-forget WhatsApp alert (non-blocking)."""
    try:
        def _send():
            send_whatsapp_sync(to_number, message)

        t = threading.Thread(target=_send, daemon=True)
        t.start()
        logger.info(f"WhatsApp alert dispatch started for {to_number}")
        return "dispatched"

    except Exception as e:
        logger.error(f"Failed to dispatch WhatsApp alert: {e}")
        return None


def send_safe_notification(user_full_name, contact_phone, safe_time_display: str, timezone_label: str | None = None):
    """Send WhatsApp 'I'm Safe' notification to a trusted contact."""
    time_fragment = safe_time_display or "just now"
    if timezone_label:
        time_fragment = f"{time_fragment} {timezone_label}"

    message_body = (
        f"✅ SAFE: {user_full_name} is now safe!\n\n"
        f"They marked themselves safe at {time_fragment}.\n\n"
        "Previous SOS alert has been resolved.\n\n"
        "- Asfalis Safety App"
    )

    result = send_whatsapp_sync(contact_phone, message_body)
    return result["success"], result.get("sid")
