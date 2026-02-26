
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
