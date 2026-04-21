"""Protection / Auto-SOS routes."""

import logging
from fastapi import APIRouter, Depends, HTTPException
from app.dependencies import get_current_user
from app.schemas.protection_schema import (
    ToggleProtectionRequest, SensorDataRequest, SensorWindowRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/toggle",
    summary="Toggle Auto SOS Protection",
    description=(
        "Enable or disable the Auto SOS protection system for the authenticated user. "
        "When enabled, sensor data submitted to `/protection/sensor-data` or `/protection/predict` "
        "is analysed and a danger detection starts a 10-second cancellation countdown. "
        "This preference is persisted to the database and survives server restarts."
    ),
)
def toggle_protection(data: ToggleProtectionRequest, user_id: str = Depends(get_current_user)):
    try:
        from app.services.protection_service import toggle_protection as _toggle
        success, msg = _toggle(user_id, data.is_active)
        if not success:
            raise HTTPException(500, detail={"code": "TOGGLE_ERROR", "message": msg})
        return {"success": True, "message": msg}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to toggle protection for user {user_id}: {e}", exc_info=True)
        raise HTTPException(500, detail={"code": "INTERNAL_ERROR", "message": str(e)})


@router.get(
    "/status",
    summary="Get Auto SOS Protection Status",
    description=(
        "Returns whether Auto SOS protection is currently active for the user "
        "and whether a Bluetooth bracelet is connected."
    ),
)
def get_protection_status(user_id: str = Depends(get_current_user)):
    from app.services.protection_service import get_protection_status as _get_status
    status = _get_status(user_id)
    return {"success": True, "data": status}


@router.post(
    "/sensor-data",
    summary="Analyze Streaming Sensor Data (Auto SOS — Flow 2)",
    description=(
        "**Flow 2 — Auto SOS via streaming sensor data.**\n\n"
        "Send a window of raw accelerometer/gyroscope data. The backend checks the "
        "magnitude against a sensitivity-based threshold (high=35%, medium=60%, low=85%).\n"
        "If **DANGER** is detected: starts a 10-second countdown, sends an FCM push to the app, "
        "and returns `alert_id` + `countdown_seconds`.\n\n"
        "The app MUST call `POST /sos/send-now` if the countdown elapses without a cancel, "
        "or `POST /sos/cancel` if the user dismisses the alert.\n\n"
        "**Sensitivity values**: `'high'` | `'medium'` (default) | `'low'`"
    ),
)
def analyze_sensor_data(data: SensorDataRequest, user_id: str = Depends(get_current_user)):
    from app.services.protection_service import analyze_sensor_data as _analyze
    readings = [{"x": r.x, "y": r.y, "z": r.z, "timestamp": r.timestamp} for r in data.data]
    result = _analyze(user_id, data.sensor_type, readings, data.sensitivity)
    return {"success": True, "data": result}


@router.post(
    "/predict",
    summary="Predict Danger from Pre-windowed Data (Auto SOS — Flow 2)",
    description=(
        "**Flow 2 — Auto SOS via pre-windowed data.**\n\n"
        "Called by the app after its on-device magnitude threshold fires. "
        "Accepts a pre-formed `[[x, y, z], ...]` window (at least 3 readings, ideally 300). "
        "If DANGER is detected:\n"
        "1. Starts the 10-second cancellation countdown.\n"
        "2. Sends an FCM push notification to the app.\n"
        "3. Returns `alert_id` + `countdown_seconds`.\n\n"
        "The app MUST call `POST /sos/send-now` after the countdown or `POST /sos/cancel` to dismiss.\n\n"
        "**Note**: GPS coordinates in the request body take priority over the last DB-saved location."
    ),
)
def predict_danger(data: SensorWindowRequest, user_id: str = Depends(get_current_user)):
    from app.services.protection_service import predict_from_window
    result = predict_from_window(
        user_id=user_id,
        window_data=data.window,
        sensor_type=data.sensor_type,
        latitude=data.latitude,
        longitude=data.longitude,
    )
    return {"success": True, "data": result}


@router.post(
    "/collect",
    summary="Collect Sensor Training Data",
    description="Accepts labelled 300-point windows from Android to improve the user's ML model.",
)
def collect_sensor_data(data: SensorWindowRequest, user_id: str = Depends(get_current_user)):
    # Currently a stub to prevent 404 for frontend team. 
    # Real logic can dump to CSV / database.
    return {"success": True, "message": "Training data collected successfully"}

