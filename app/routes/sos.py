"""SOS routes — converted to FastAPI."""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.extensions import db
from app.models.sos_alert import SOSAlert
from app.models.user import User
from app.dependencies import get_current_user
from app.services.sos_service import trigger_sos, dispatch_sos, cancel_sos, mark_user_safe
from app.utils.timezone_utils import format_datetime_for_response, get_timezone_for_country

logger = logging.getLogger(__name__)
router = APIRouter()


class TriggerSOSRequest(BaseModel):
    latitude: float = 0.0
    longitude: float = 0.0
    trigger_type: str = 'manual'
    message: Optional[str] = None


class WhatsAppTestRequest(BaseModel):
    to_number: str
    message: Optional[str] = "This is a test message from Asfalis."


def _expire_stale_countdowns(user_id: str):
    """Auto-expire countdown alerts older than 60 seconds."""
    from datetime import datetime, timedelta
    cutoff = datetime.utcnow() - timedelta(seconds=60)
    SOSAlert.query.filter(
        SOSAlert.user_id == user_id,
        SOSAlert.status == 'countdown',
        SOSAlert.triggered_at < cutoff
    ).update({'status': 'cancelled', 'resolution_type': 'expired'}, synchronize_session=False)
    db.session.commit()


@router.post("/trigger", status_code=201)
def trigger_sos_route(data: TriggerSOSRequest, user_id: str = Depends(get_current_user)):
    from app.models.trusted_contact import TrustedContact
    if TrustedContact.query.filter_by(user_id=user_id).count() == 0:
        raise HTTPException(400, detail={"code": "NO_CONTACTS",
                                         "message": "Add at least one emergency contact before sending an SOS."})

    alert, msg = trigger_sos(user_id, data.latitude, data.longitude, trigger_type=data.trigger_type)
    if not alert:
        raise HTTPException(400, detail={"code": "SOS_ERROR", "message": msg})

    user = db.session.get(User, user_id)
    tz = get_timezone_for_country(user.country).zone if user and user.country else 'UTC'

    return {"success": True, "message": msg, "data": {
        "alert_id": alert.id,
        "trigger_type": alert.trigger_type,
        "status": alert.status,
        "triggered_at": format_datetime_for_response(alert.triggered_at, user.country if user else None),
        "timezone": tz,
    }}


@router.post("/send-now")
def send_sos_now(body: dict, user_id: str = Depends(get_current_user)):
    alert_id = body.get('alert_id')
    result = dispatch_sos(alert_id, user_id)
    if not result.get('success'):
        raise HTTPException(400, detail={"code": "DISPATCH_ERROR",
                                         "message": result.get('message', 'Failed to dispatch SOS.')})
    return result


@router.post("/cancel")
def cancel_sos_route(body: dict, user_id: str = Depends(get_current_user)):
    alert_id = body.get('alert_id')
    if not alert_id:
        # IoT fallback: find the latest countdown
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


@router.post("/safe")
def mark_safe_route(body: dict, user_id: str = Depends(get_current_user)):
    alert_id = body.get('alert_id')
    success, msg = mark_user_safe(alert_id, user_id)
    if not success:
        raise HTTPException(400, detail={"code": "SAFE_ERROR", "message": msg})
    return {"success": True, "message": msg}


@router.get("/history")
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


@router.post("/test-whatsapp")
def test_whatsapp(data: WhatsAppTestRequest, user_id: str = Depends(get_current_user)):
    from app.services.whatsapp_service import send_whatsapp_sync
    result = send_whatsapp_sync(data.to_number, data.message)
    return {"success": result["success"], "data": result}
