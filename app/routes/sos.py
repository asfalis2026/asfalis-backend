"""SOS routes — converted to FastAPI."""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.extensions import db
from app.models.sos_alert import SOSAlert
from app.models.user import User
from app.dependencies import get_current_user
from app.services.sos_service import (
    trigger_sos, dispatch_sos, cancel_sos, mark_user_safe,
    COUNTDOWN_SECONDS, COUNTDOWN_EXPIRY_SECONDS,
)
from app.utils.timezone_utils import format_datetime_for_response, get_timezone_for_country

logger = logging.getLogger(__name__)
router = APIRouter()


class TriggerSOSRequest(BaseModel):
    latitude: float = 0.0
    longitude: float = 0.0
    # Flow 1: 'manual' | 'iot_button'
    # Flow 2: 'auto_fall' | 'auto_shake'
    # Flow 3: 'hardware_distress'  (app sends this after BT disconnect/out-of-radius + 10s reconnect window)
    trigger_type: str = 'manual'
    message: Optional[str] = None


class WhatsAppTestRequest(BaseModel):
    to_number: str
    message: Optional[str] = "This is a test message from Asfalis."


def _expire_stale_countdowns(user_id: str):
    """Auto-expire countdown alerts older than COUNTDOWN_EXPIRY_SECONDS."""
    from datetime import datetime, timedelta
    cutoff = datetime.utcnow() - timedelta(seconds=COUNTDOWN_EXPIRY_SECONDS)
    SOSAlert.query.filter(
        SOSAlert.user_id == user_id,
        SOSAlert.status == 'countdown',
        SOSAlert.triggered_at < cutoff
    ).update({'status': 'cancelled', 'resolution_type': 'expired'}, synchronize_session=False)
    db.session.commit()


@router.post(
    "/trigger",
    status_code=201,
    summary="Trigger SOS Alert (Start Countdown)",
    description=(
        "Start an SOS alert for the authenticated user. Creates an alert with status `countdown` "
        "and returns `alert_id` + `countdown_seconds`. The app must show a cancellation UI "
        "for the duration of the countdown.\n\n"
        "**`trigger_type` values:**\n"
        "- `'manual'` — user pressed the in-app SOS button (Flow 1)\n"
        "- `'iot_button'` — hardware button press relayed by the app (Flow 1)\n"
        "- `'auto_fall'` — accelerometer fall detected by ML (Flow 2, usually via /protection/predict)\n"
        "- `'auto_shake'` — gyroscope shake detected by ML (Flow 2)\n"
        "- `'hardware_distress'` — app detected bracelet disconnect/out-of-radius after 10s reconnect window (Flow 3)\n\n"
        "After the countdown elapses without a cancel, the app calls `POST /sos/send-now` to dispatch. "
        "For `manual` and `iot_button` cancels, an 'I am Safe' WhatsApp message is sent. "
        "For auto/hardware_distress cancels, the window is labelled SAFE for ML retraining — no WhatsApp message."
    ),
)
def trigger_sos_route(data: TriggerSOSRequest, user_id: str = Depends(get_current_user)):
    from app.models.trusted_contact import TrustedContact
    if TrustedContact.query.filter_by(user_id=user_id).count() == 0:
        raise HTTPException(400, detail={"code": "NO_CONTACTS",
                                         "message": "Add at least one emergency contact before sending an SOS."})

    alert, msg, countdown_seconds = trigger_sos(
        user_id, data.latitude, data.longitude, trigger_type=data.trigger_type
    )
    if not alert:
        raise HTTPException(400, detail={"code": "SOS_ERROR", "message": msg})

    from datetime import datetime, timedelta
    user = db.session.get(User, user_id)
    tz = get_timezone_for_country(user.country).zone if user and user.country else 'UTC'
    countdown_expires_at = (
        alert.triggered_at + timedelta(seconds=countdown_seconds)
    ).isoformat() + 'Z'

    return {"success": True, "message": msg, "data": {
        "alert_id": alert.id,
        "trigger_type": alert.trigger_type,
        "status": alert.status,
        "triggered_at": format_datetime_for_response(alert.triggered_at, user.country if user else None),
        "timezone": tz,
        "countdown_seconds": countdown_seconds,
        "countdown_expires_at": countdown_expires_at,
    }}


@router.post(
    "/send-now",
    summary="Dispatch SOS Now (After Countdown)",
    description=(
        "Dispatch a previously triggered SOS alert immediately. "
        "Transitions the alert from `countdown` → `sent` and sends WhatsApp messages to all trusted contacts. "
        "Returns a `delivery_report` array showing success/failure per contact.\n\n"
        "Call this when the countdown elapses without a cancel. "
        "Calling it on an already-sent or cancelled alert returns a 400 error."
    ),
)
def send_sos_now(body: dict, user_id: str = Depends(get_current_user)):
    alert_id = body.get('alert_id')
    success, msg, delivery_report = dispatch_sos(alert_id, user_id)
    if not success:
        raise HTTPException(400, detail={"code": "DISPATCH_ERROR", "message": msg})
    return {"success": True, "message": msg, "data": {"delivery_report": delivery_report}}


@router.post(
    "/cancel",
    summary="Cancel SOS (During Countdown)",
    description=(
        "Cancel an active SOS countdown. Behaviour differs by `trigger_type` of the alert:\n\n"
        "- **`manual` / `iot_button`**: Sends 'I am Safe' WhatsApp to all trusted contacts.\n"
        "- **`auto_fall` / `auto_shake`**: Marks the ML training window as SAFE (label=0) for retraining. No WhatsApp message.\n"
        "- **`hardware_distress`**: Same as auto — marks window SAFE, no WhatsApp message (app handles reconnect).\n\n"
        "If `alert_id` is omitted, the latest active countdown for the user is cancelled (IoT fallback)."
    ),
)
def cancel_sos_route(body: dict, user_id: str = Depends(get_current_user)):
    alert_id = body.get('alert_id')
    if not alert_id:
        latest = SOSAlert.query.filter(
            SOSAlert.user_id == user_id,
            SOSAlert.status == 'countdown'
        ).order_by(SOSAlert.triggered_at.desc()).first()
        if latest:
            alert_id = latest.id

    success, msg = cancel_sos(alert_id, user_id)
    if not success:
        raise HTTPException(400, detail={"code": "CANCEL_ERROR", "message": msg})
    return {"success": True, "message": msg}


@router.post(
    "/safe",
    summary="Mark User as Safe (Post-Dispatch)",
    description=(
        "Mark a dispatched SOS alert as resolved-safe after the emergency has passed. "
        "Transitions the alert status to `resolved` and sends a follow-up 'I am Safe' "
        "WhatsApp message to all trusted contacts. "
        "Returns `contacts_notified` count."
    ),
)
def mark_safe_route(body: dict, user_id: str = Depends(get_current_user)):
    alert_id = body.get('alert_id')
    success, msg, contacts_notified = mark_user_safe(alert_id, user_id)
    if not success:
        raise HTTPException(400, detail={"code": "SAFE_ERROR", "message": msg})
    return {"success": True, "message": msg, "data": {"contacts_notified": contacts_notified}}


@router.get(
    "/history",
    summary="Get SOS Alert History",
    description=(
        "Returns all SOS alerts for the user in reverse chronological order. "
        "Stale `countdown` alerts older than the expiry window are auto-cancelled before returning. "
        "Each alert includes `status`, `trigger_type`, `triggered_at` (localized), and `resolution_type`."
    ),
)
def get_sos_history(user_id: str = Depends(get_current_user)):
    _expire_stale_countdowns(user_id)
    alerts = SOSAlert.query.filter_by(user_id=user_id)\
        .order_by(SOSAlert.triggered_at.desc()).all()
    user = db.session.get(User, user_id)
    country = user.country if user else None
    return {"success": True, "data": [
        {**alert.to_dict(), "triggered_at": format_datetime_for_response(alert.triggered_at, country)}
        for alert in alerts
    ]}


@router.get("/countdown/{alert_id}")
def get_countdown_status(alert_id: str, user_id: str = Depends(get_current_user)):
    """
    Poll the server-side countdown state for an active SOS alert.

    The mobile app calls this after receiving an alert_id from POST /trigger.
    It lets the app verify the countdown is still valid (not expired or already
    dispatched/cancelled) and provides an authoritative `seconds_remaining`
    value to re-sync the on-screen timer if needed.

    Lifecycle:
      - status='countdown'  → countdown is alive; seconds_remaining > 0
      - status='sent'       → server already dispatched (or app called /send-now)
      - status='cancelled'  → user or h/w cancelled during countdown
      - status='expired'    → countdown window elapsed without action (cleanup ran)
    """
    from datetime import datetime, timedelta

    alert = SOSAlert.query.filter_by(id=alert_id, user_id=user_id).first()
    if not alert:
        raise HTTPException(404, detail={"code": "NOT_FOUND",
                                         "message": "Alert not found."})

    response = {
        "alert_id": alert.id,
        "status": alert.status,
        "trigger_type": alert.trigger_type,
        "triggered_at": alert.triggered_at.isoformat() + 'Z' if alert.triggered_at else None,
        "countdown_seconds": COUNTDOWN_SECONDS,
        "seconds_remaining": 0,
        "countdown_expires_at": None,
        "is_active": False,
    }

    if alert.status == 'countdown' and alert.triggered_at:
        expires_at = alert.triggered_at + timedelta(seconds=COUNTDOWN_SECONDS)
        now = datetime.utcnow()
        seconds_remaining = (expires_at - now).total_seconds()

        if seconds_remaining > 0:
            # Countdown is still live
            response["is_active"] = True
            response["seconds_remaining"] = round(seconds_remaining, 2)
            response["countdown_expires_at"] = expires_at.isoformat() + 'Z'
        else:
            # Window elapsed — the app should call /send-now immediately.
            # The backend stale-cleanup (COUNTDOWN_EXPIRY_SECONDS=60s) will
            # cancel this alert if /send-now is never called.
            response["is_active"] = False
            response["seconds_remaining"] = 0
            response["countdown_expires_at"] = expires_at.isoformat() + 'Z'
            response["message"] = "Countdown window elapsed. Call POST /sos/send-now to dispatch."

    return {"success": True, "data": response}


@router.post(
    "/test-whatsapp",
    summary="Test WhatsApp Delivery",
    description="Send a test WhatsApp message to a given number to verify Twilio/WhatsApp configuration.",
)
def test_whatsapp(data: WhatsAppTestRequest, user_id: str = Depends(get_current_user)):
    from app.services.whatsapp_service import send_whatsapp_sync
    result = send_whatsapp_sync(data.to_number, data.message)
    return {"success": result["success"], "data": result}
