
from flask import current_app
from twilio.rest import Client
from celery import shared_task
import logging

logger = logging.getLogger(__name__)

@shared_task(ignore_result=True)
def send_whatsapp_task(to_number, message, account_sid, auth_token, whatsapp_from):
    """
    Background task to send a WhatsApp message.
    """
    try:
        if not all([account_sid, auth_token, whatsapp_from]):
            logger.warning("Twilio WhatsApp credentials not configured, skipping alert.")
            return

        client = Client(account_sid, auth_token)

        # Ensure the 'to' number has the whatsapp: prefix
        if not to_number.startswith('whatsapp:'):
            to_number = f'whatsapp:{to_number}'

        msg = client.messages.create(
            from_=whatsapp_from,
            body=message,
            to=to_number
        )
        logger.info(f"WhatsApp alert sent: {msg.sid}")
    except Exception as e:
        logger.error(f"Failed to send WhatsApp alert: {e}")

def send_whatsapp_alert(to_number, message):
    """Queue a WhatsApp message via Twilio.

    Args:
        to_number: Recipient WhatsApp number in E.164 format (e.g. +919876543210).
                   Will be prefixed with 'whatsapp:' automatically.
        message: The alert message body.

    Returns:
        The task ID on success, None on failure.
    """
    try:
        account_sid = current_app.config.get('TWILIO_ACCOUNT_SID')
        auth_token = current_app.config.get('TWILIO_AUTH_TOKEN')
        whatsapp_from = current_app.config.get('TWILIO_WHATSAPP_FROM')
        
        # Dispatch to Celery
        send_whatsapp_task.delay(to_number, message, account_sid, auth_token, whatsapp_from)
        current_app.logger.info(f"WhatsApp alert task queued for {to_number}")
        return "queued"

    except Exception as e:
        current_app.logger.error(f"Failed to queue WhatsApp alert: {e}")
        return None
