# Dead Code - Unused WhatsApp Functions
# These functions were never called and are kept here for reference only

from app.config import settings
from twilio.rest import Client
import logging
import threading

logger = logging.getLogger(__name__)


def send_whatsapp_alert(to_number, message):
    """
    DEPRECATED: Fire-and-forget WhatsApp alert (non-blocking).
    Currently using send_whatsapp_sync() directly instead.
    """
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


# Note: send_whatsapp_sync() is still actively used and should NOT be moved here
