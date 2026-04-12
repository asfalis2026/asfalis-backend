"""Device routes — converted to FastAPI."""

import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.extensions import db
from app.models.user import User
from app.models.device import ConnectedDevice
from app.models.sos_alert import SOSAlert
from app.config import settings
from app.dependencies import get_current_user
from app.services.sos_service import trigger_sos

logger = logging.getLogger(__name__)
router = APIRouter()


class DeviceRegisterRequest(BaseModel):
    device_name: str
    device_mac: str
    firmware_version: Optional[str] = None


class ButtonEventRequest(BaseModel):
    device_mac: str
    latitude: float = 0.0
    longitude: float = 0.0


@router.post("/register", status_code=201)
def register_device(data: DeviceRegisterRequest, user_id: str = Depends(get_current_user)):
    device = ConnectedDevice.query.filter_by(device_mac=data.device_mac).first()
    if device:
        device.user_id = user_id
        device.is_connected = True
        device.last_seen = datetime.utcnow()
        device.last_button_press_at = None
    else:
        device = ConnectedDevice(
            user_id=user_id,
            device_name=data.device_name,
            device_mac=data.device_mac,
            firmware_version=data.firmware_version,
            is_connected=True,
            last_seen=datetime.utcnow()
        )
        db.session.add(device)
    db.session.commit()
    return {"success": True, "data": device.to_dict()}


@router.get("/status")
def get_device_status(user_id: str = Depends(get_current_user)):
    device = ConnectedDevice.query.filter_by(user_id=user_id)\
        .order_by(ConnectedDevice.last_seen.desc()).first()
    return {"success": True, "data": device.to_dict() if device else None}


@router.put("/{device_id}/status")
def update_device_status(device_id: str, body: dict, user_id: str = Depends(get_current_user)):
    device = ConnectedDevice.query.filter_by(id=device_id, user_id=user_id).first()
    if not device:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Device not found."})
    if 'is_connected' in body:
        device.is_connected = body['is_connected']
    device.last_seen = datetime.utcnow()
    db.session.commit()
    return {"success": True, "data": device.to_dict()}


@router.post("/button-event")
def iot_button_event(data: ButtonEventRequest, user_id: str = Depends(get_current_user)):
    device = ConnectedDevice.query.filter_by(device_mac=data.device_mac, user_id=user_id).first()
    if not device:
        raise HTTPException(404, detail={"code": "NOT_FOUND",
                                         "message": "Device not found or not paired."})

    double_tap_window = settings.IOT_DOUBLE_TAP_WINDOW_SECONDS
    now = datetime.utcnow()
    is_double_tap = False
    if device.last_button_press_at:
        elapsed = (now - device.last_button_press_at).total_seconds()
        if elapsed <= double_tap_window:
            is_double_tap = True

    device.last_seen = now
    device.last_button_press_at = now
    device.is_connected = True
    db.session.commit()

    if is_double_tap:
        active_alert = (
            SOSAlert.query.filter(
                SOSAlert.user_id == user_id,
                SOSAlert.status.in_(['countdown', 'sent'])
            ).order_by(SOSAlert.triggered_at.desc()).first()
        )
        if not active_alert:
            return {"success": True, "action": "cancelled",
                    "message": "Double-tap received but no active SOS found."}

        from app.services.sos_service import cancel_sos
        success, msg = cancel_sos(active_alert.id, user_id)
        if not success:
            raise HTTPException(400, detail={"code": "ERROR", "message": msg})
        return {"success": True, "action": "cancelled", "message": msg,
                "data": {"alert_id": active_alert.id}}

    # Single press
    from app.models.trusted_contact import TrustedContact
    if TrustedContact.query.filter_by(user_id=user_id).count() == 0:
        raise HTTPException(400, detail={"code": "NO_CONTACTS",
                                         "message": "Add at least one emergency contact before sending an SOS."})

    alert, msg, _ = trigger_sos(user_id, data.latitude, data.longitude, trigger_type='iot_button')
    if not alert:
        raise HTTPException(400, detail={"code": "ERROR", "message": msg})

    from app.utils.timezone_utils import format_datetime_for_response, get_timezone_for_country
    user = db.session.get(User, user_id)
    tz = get_timezone_for_country(user.country).zone if user and user.country else 'UTC'

    return {"success": True, "action": "triggered", "message": msg, "data": {
        "alert_id": alert.id,
        "trigger_type": alert.trigger_type,
        "status": alert.status,
        "triggered_at": format_datetime_for_response(alert.triggered_at, user.country if user else None),
        "timezone": tz,
    }}


@router.post("/alert")
def device_alert(body: dict):
    mac = body.get('device_mac')
    if not mac:
        raise HTTPException(400, detail={"code": "VALIDATION_ERROR", "message": "Missing MAC."})
    device = ConnectedDevice.query.filter_by(device_mac=mac).first()
    if not device:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Device not found."})
    from app.services.location_service import get_last_location
    last_loc = get_last_location(device.user_id)
    lat = last_loc.latitude if last_loc else 0.0
    lng = last_loc.longitude if last_loc else 0.0
    alert, msg, _ = trigger_sos(device.user_id, lat, lng, trigger_type='bracelet')
    return {"success": True, "message": msg}


@router.post(
    "/cancel-sos",
    summary="Hardware Cancel SOS (Two-Click Bridge)",
    description=(
        "**Hardware-only bridge endpoint** — No auth token required.\n\n"
        "Called by the mobile app on behalf of the bracelet after a two-click hardware "
        "cancel signal. Identifies the user via `device_mac` and cancels the latest active "
        "`countdown` or `sent` SOS alert.\n\n"
        "**Flow 1 & 3 (h/w cancel path)**:\n"
        "- Bracelet sends two clicks → App receives BLE event → App calls this endpoint\n"
        "- For `manual`/`iot_button` alerts: sends 'I am Safe' WhatsApp to contacts\n"
        "- For `auto_*`/`hardware_distress` alerts: labels the window as SAFE for ML retraining\n\n"
        "**Body**: `{ \"device_mac\": \"AA:BB:CC:DD:EE:FF\" }`"
    ),
)
def hardware_cancel_sos(body: dict):
    mac = body.get('device_mac')
    if not mac:
        raise HTTPException(400, detail={"code": "VALIDATION_ERROR", "message": "Missing device_mac."})

    device = ConnectedDevice.query.filter_by(device_mac=mac).first()
    if not device:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Device not found or not paired."})

    # Find the latest active (countdown or sent) alert for this device's user
    active_alert = (
        SOSAlert.query.filter(
            SOSAlert.user_id == device.user_id,
            SOSAlert.status.in_(['countdown', 'sent'])
        ).order_by(SOSAlert.triggered_at.desc()).first()
    )

    if not active_alert:
        return {"success": True, "action": "no_op",
                "message": "No active SOS found for this device."}

    from app.services.sos_service import cancel_sos
    success, msg = cancel_sos(active_alert.id, device.user_id)
    if not success:
        raise HTTPException(400, detail={"code": "CANCEL_ERROR", "message": msg})

    # Update device last-seen
    device.last_seen = datetime.utcnow()
    db.session.commit()

    return {"success": True, "action": "cancelled", "message": msg,
            "data": {"alert_id": active_alert.id}}


@router.delete("/{device_id}")
def delete_device(device_id: str, user_id: str = Depends(get_current_user)):
    device = ConnectedDevice.query.filter_by(id=device_id, user_id=user_id).first()
    if not device:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Device not found."})
    db.session.delete(device)
    db.session.commit()
    return {"success": True, "message": "Device removed."}
