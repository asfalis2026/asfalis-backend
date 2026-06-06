"""Twilio webhook routes for status callbacks."""

import logging
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from app.extensions import db
from app.models.sos_alert import SOSAlert

logger = logging.getLogger(__name__)
router = APIRouter()


class TwilioStatusCallback(BaseModel):
    """Model for Twilio status callback parameters."""
    MessageSid: str
    MessageStatus: str
    To: str = ""
    ErrorCode: str = ""
    ErrorMessage: str = ""


# Map Twilio status values to our internal status tracking
# Twilio statuses: queued, sent, delivered, failed, undelivered, cancelled
FAILED_STATUSES = {'failed', 'undelivered', 'cancelled'}
SUCCESS_STATUSES = {'delivered', 'sent'}


@router.post(
    "/webhook",
    summary="Twilio Status Callback Webhook",
    description=(
        "Endpoint to receive Twilio WhatsApp status callbacks. "
        "When Twilio reports a message as failed or undelivered, "
        "this endpoint updates the corresponding SOSAlert status to 'failed'.\n\n"
        "Twilio sends callbacks for: queued, sent, delivered, failed, undelivered, cancelled"
    ),
)
async def twilio_status_webhook(request: Request):
    """
    Handle Twilio status callback webhooks.

    Twilio will POST to this endpoint with:
    - MessageSid: The unique identifier for the message
    - MessageStatus: queued, sent, delivered, failed, undelivered, cancelled
    - To: The recipient phone number
    - ErrorCode: Error code if delivery failed
    - ErrorMessage: Error message if delivery failed
    """
    # Get form data from Twilio (they send application/x-www-form-urlencoded)
    form_data = await request.form()

    message_sid = form_data.get("MessageSid")
    message_status = form_data.get("MessageStatus")
    to_number = form_data.get("To", "")
    error_code = form_data.get("ErrorCode", "")
    error_message = form_data.get("ErrorMessage", "")

    logger.info(
        f"Twilio callback received: sid={message_sid}, status={message_status}, "
        f"to={to_number}, error_code={error_code}"
    )

    if not message_sid:
        logger.warning("Twilio webhook missing MessageSid")
        raise HTTPException(400, detail="Missing MessageSid")

    # Find the SOSAlert that has this message_sid
    # We need to search through all alerts to find one with this sid
    alerts = SOSAlert.query.filter(
        SOSAlert.message_sids.isnot(None)
    ).all()

    found_alert = None
    for alert in alerts:
        if alert.message_sids:
            # message_sids is a dict: {phone_number: message_sid}
            if message_sid in alert.message_sids.values():
                found_alert = alert
                break

    if not found_alert:
        logger.warning(f"No SOSAlert found for message_sid: {message_sid}")
        # Return 200 to Twilio even if we don't find it (prevent retries)
        return {"success": True, "message": "Callback received"}

    # Check if this is a failure status
    if message_status in FAILED_STATUSES:
        old_status = found_alert.status
        # Only update if not already in a terminal state
        if found_alert.status not in ['cancelled', 'resolved', 'failed']:
            found_alert.status = 'failed'
            logger.info(
                f"Marking SOSAlert {found_alert.id} as failed due to "
                f"Twilio status: {message_status} (error_code: {error_code})"
            )
            db.session.commit()
        else:
            logger.info(
                f"SOSAlert {found_alert.id} already in terminal state: {old_status}, "
                f"ignoring Twilio callback"
            )
    elif message_status in SUCCESS_STATUSES:
        logger.info(
            f"Message {message_sid} delivered successfully for alert {found_alert.id}"
        )
    else:
        logger.info(
            f"Message {message_sid} status update: {message_status} "
            f"(not a success or failure)"
        )

    return {"success": True, "message": "Callback processed"}
