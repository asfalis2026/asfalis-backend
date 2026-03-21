"""Protection / Auto-SOS routes — converted to FastAPI."""

import logging
import threading
from fastapi import APIRouter, Depends, HTTPException
from app.dependencies import get_current_user
from app.schemas.protection_schema import (
    ToggleProtectionRequest, SensorDataRequest,
    SensorWindowRequest, SensorTrainingRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/toggle")
def toggle_protection(data: ToggleProtectionRequest, user_id: str = Depends(get_current_user)):
    from app.services.protection_service import toggle_auto_sos
    result = toggle_auto_sos(user_id, data.is_active)
    return {"success": True, "data": result}


@router.get("/status")
def get_protection_status(user_id: str = Depends(get_current_user)):
    from app.services.protection_service import is_protection_active
    from app.models.device import ConnectedDevice
    active = is_protection_active(user_id)
    device = ConnectedDevice.query.filter_by(user_id=user_id)\
        .order_by(ConnectedDevice.last_seen.desc()).first()
    return {"success": True, "data": {
        "is_active": active,
        "iot_connected": device.is_connected if device else False,
        "device": device.to_dict() if device else None,
    }}


@router.post("/sensor-data")
def analyze_sensor_data(data: SensorDataRequest, user_id: str = Depends(get_current_user)):
    from app.services.protection_service import analyze_sensor_data as _analyze
    readings = [{"x": r.x, "y": r.y, "z": r.z, "timestamp": r.timestamp} for r in data.data]
    result = _analyze(user_id, data.sensor_type, readings, data.sensitivity)
    return {"success": True, "data": result}


@router.post("/predict")
def predict_danger(data: SensorWindowRequest, user_id: str = Depends(get_current_user)):
    from app.services.protection_service import predict_from_window
    result = predict_from_window(
        user_id=user_id,
        window=data.window,
        sensor_type=data.sensor_type,
        latitude=data.latitude,
        longitude=data.longitude,
    )
    return {"success": True, "data": result}


@router.post("/collect")
def collect_training_data(data: SensorTrainingRequest, user_id: str = Depends(get_current_user)):
    from app.services.protection_service import save_training_data
    readings = [{"x": r.x, "y": r.y, "z": r.z, "timestamp": r.timestamp} for r in data.data]
    success, msg = save_training_data(user_id, data.sensor_type, readings, label=data.label, is_verified=True)
    if not success:
        raise HTTPException(500, detail={"code": "SAVE_ERROR", "message": msg})
    return {"success": True, "message": msg}


@router.post("/train-model")
def train_model(user_id: str = Depends(get_current_user)):
    from app.services.protection_service import retrain_model, _reset_model_cache
    from app.database import ScopedSession

    def _train_in_background():
        try:
            success, msg = retrain_model(user_id)
            if success:
                _reset_model_cache()
            logger.info(f"Background training complete for user {user_id}: {msg}")
        except Exception as e:
            logger.error(f"Background training error for user {user_id}: {e}")
        finally:
            ScopedSession.remove()  # clean up thread-local DB session

    thread = threading.Thread(target=_train_in_background, daemon=True)
    thread.start()
    return {"success": True, "message": "Model training started in background."}


@router.post("/feedback/{alert_id}")
def submit_feedback(alert_id: str, body: dict, user_id: str = Depends(get_current_user)):
    is_false_alarm = body.get('is_false_alarm', False)
    from app.services.protection_service import submit_sos_feedback
    success, msg = submit_sos_feedback(user_id, alert_id, is_false_alarm)
    if not success:
        raise HTTPException(400, detail={"code": "FEEDBACK_ERROR", "message": msg})
    return {"success": True, "message": msg}
