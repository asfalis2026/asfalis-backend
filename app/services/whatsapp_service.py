
from flask import current_app
from twilio.rest import Client
import logging
import threading

logger = logging.getLogger(__name__)


def send_whatsapp_alert(to_number, message):
    """
    Send a WhatsApp message via Twilio directly in a background thread.
    No external task queue required.

    Args:
        to_number: Recipient WhatsApp number in E.164 format (e.g. +919876543210).
                   Will be prefixed with 'whatsapp:' automatically.
        message: The alert message body.
    """
    try:
        account_sid = current_app.config.get('TWILIO_ACCOUNT_SID')
        auth_token = current_app.config.get('TWILIO_AUTH_TOKEN')
        whatsapp_from = current_app.config.get('TWILIO_WHATSAPP_FROM')

        if not all([account_sid, auth_token, whatsapp_from]):
            logger.warning("Twilio WhatsApp credentials not configured, skipping alert.")
            return None

        # Ensure the 'to' number has the whatsapp: prefix
        if not to_number.startswith('whatsapp:'):
            to_number = f'whatsapp:{to_number}'

        # Use a thread so we don't block the HTTP response
        app = current_app._get_current_object()

        def _send():
            with app.app_context():
                try:
                    client = Client(account_sid, auth_token)
                    msg = client.messages.create(
                        from_=whatsapp_from,
                        body=message,
                        to=to_number
                    )
                    logger.info(f"WhatsApp alert sent: {msg.sid}")
                except Exception as e:
                    logger.error(f"Failed to send WhatsApp alert: {e}")

        t = threading.Thread(target=_send, daemon=True)
        t.start()
        current_app.logger.info(f"WhatsApp alert dispatch started for {to_number}")
        return "dispatched"

    except Exception as e:
        current_app.logger.error(f"Failed to dispatch WhatsApp alert: {e}")
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

