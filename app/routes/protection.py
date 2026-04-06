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


@router.post(
    "/toggle",
    summary="Toggle Auto SOS Protection",
    description=(
        "Enable or disable the Auto SOS protection system for the authenticated user. "
        "When enabled, sensor data submitted to `/protection/sensor-data` or `/protection/predict` "
        "will be run through the ML model. A danger prediction starts a 10-second cancellation countdown. "
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
        "**Flow 2 — Auto ML SOS via streaming sensor data.**\n\n"
        "Send a 300-reading window of raw accelerometer/gyroscope data. The backend:\n"
        "1. Extracts 39 statistical features from the window.\n"
        "2. Runs the ML model with a sensitivity-based threshold (high=35%, medium=60%, low=85%).\n"
        "3. Auto-saves the window as unverified training data.\n"
        "4. If **DANGER**: starts a 10-second countdown, sends an FCM push to the app, "
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
        "**Flow 2 — Auto ML SOS via pre-windowed data.**\n\n"
        "Called by the app after its on-device magnitude threshold fires. "
        "Accepts a pre-formed `[[x, y, z], ...]` window (at least 3 readings, ideally 300). "
        "The backend runs the ML model and, if DANGER is predicted:\n"
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
    summary="Collect Labeled Training Window (Calibration)",
    description=(
        "Submit a raw labeled sensor window for ML model calibration. "
        "The backend extracts 39 statistical features and stores **one** `sensor_training_data` row "
        "(not one per reading). These rows are marked `is_verified=True` immediately.\n\n"
        "**`label`** accepts: `0` / `'safe'` / `'normal'` / `'no_fall'` → SAFE label; "
        "`1` / `'fall'` / `'danger'` / `'alert'` → DANGER label.\n\n"
        "**`dataset_name`** (optional): motion category tag, e.g. `'fast_walking'`, `'free_fall'`.\n\n"
        "**`motion_description`** (optional): free-text annotation, e.g. `'DANGER — Highheight Free Fall'`.\n\n"
        "After collecting both SAFE and DANGER windows, trigger retraining via `POST /protection/train-model`."
    ),
)
def collect_training_data(data: SensorTrainingRequest, user_id: str = Depends(get_current_user)):
    from app.services.protection_service import save_training_data
    window = [[r.x, r.y, r.z] for r in data.window]
    success, msg = save_training_data(
        user_id=user_id,
        window_data=window,
        label=data.label,
        is_verified=True,
        dataset_name=data.dataset_name,
        motion_description=data.motion_description,
    )
    if not success:
        raise HTTPException(500, detail={"code": "SAVE_ERROR", "message": msg})
    return {"success": True, "message": msg}


@router.post(
    "/train-model",
    summary="Retrain Personalized ML Model",
    description=(
        "Trigger a background retraining of the LightGBM Auto SOS model using all "
        "`is_verified=True` windows in `sensor_training_data`. Each row is already a "
        "39-feature vector so no re-extraction is needed.\n\n"
        "**Requirements**: Must have both SAFE (label=0) and DANGER (label=1) verified windows.\n\n"
        "Runs asynchronously. Returns immediately with a 200. "
        "The new model version is tagged `v3.x` and activated in the DB upon completion. "
        "The in-memory model cache is refreshed so the next prediction uses the new model."
    ),
)
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
            ScopedSession.remove()

    thread = threading.Thread(target=_train_in_background, daemon=True)
    thread.start()
    return {"success": True, "message": "Model training started in background."}


@router.post(
    "/feedback/{alert_id}",
    summary="Submit SOS Feedback (Correct ML Label)",
    description=(
        "Correct the ML model's label for a specific Auto SOS event. "
        "Finds the `sensor_training_data` window linked to this alert via `sos_alert_id` "
        "and updates its label + marks it `is_verified=True`.\n\n"
        "- `is_false_alarm: true`  → re-labels as SAFE (0) — user confirms it was NOT real danger.\n"
        "- `is_false_alarm: false` → confirms as DANGER (1).\n\n"
        "If the alert is still in `countdown` state and `is_false_alarm=true`, "
        "the alert is also cancelled automatically.\n\n"
        "Corrected windows are used on the next `POST /protection/train-model` run."
    ),
)
def submit_feedback(alert_id: str, body: dict, user_id: str = Depends(get_current_user)):
    is_false_alarm = body.get('is_false_alarm', False)
    from app.services.protection_service import submit_sos_feedback
    success, msg = submit_sos_feedback(user_id, alert_id, is_false_alarm)
    if not success:
        raise HTTPException(400, detail={"code": "FEEDBACK_ERROR", "message": msg})
    return {"success": True, "message": msg}
