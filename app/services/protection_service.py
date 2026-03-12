
import os
import time
import numpy as np
import joblib
from flask import current_app

from app.services.sos_service import trigger_sos

# ---------------------------------------------------------------------------
# Model loading (once at import time)
# ---------------------------------------------------------------------------
_MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'model.pkl')
_model = None

def _get_model():
    """Lazy-load the ML model from the Database (or fallback to file)."""
    global _model
    if _model is None:
        try:
            # Try loading from DB first
            from app.models.ml_model import MLModel
            from app.extensions import db
            import io
            
            # Need app context if running outside request (e.g. tests)
            # But usually this is called within a request or background task
            active_model = MLModel.query.filter_by(is_active=True).order_by(MLModel.created_at.desc()).first()
            
            if active_model:
                with io.BytesIO(active_model.data) as f:
                    _model = joblib.load(f)
                print(f"✅ Loaded ML model {active_model.version} from DB")
                return _model
            
            # Fallback to file if no DB model
            if os.path.exists(_MODEL_PATH):
                _model = joblib.load(_MODEL_PATH)
                print(f"⚠️ Loaded fallback model from {_MODEL_PATH}")
            else:
                print("❌ No active model found in DB or file.")
                
        except Exception as e:
            print(f"❌ Failed to load model: {e}")
            
    return _model


# ---------------------------------------------------------------------------
# In-memory stores
# ---------------------------------------------------------------------------
# Active protection toggle per user
active_protection_users = {}

# Auto-SOS cooldown tracker: user_id -> last AUTO SOS trigger timestamp (10 min)
_sos_cooldown = {}
SOS_COOLDOWN_SECONDS = 600  # 10 minutes between Auto SOS triggers

# Manual SOS cooldown tracker: user_id -> last MANUAL SOS trigger timestamp (20 s)
# Kept separate so a manual SOS never blocks an auto-SOS and vice-versa.
_manual_sos_cooldown = {}
MANUAL_SOS_COOLDOWN_SECONDS = 20

# Maps the hardware sensor_type (from the client/schema) to the valid
# DB trigger_type enum value in sos_alerts.trigger_type_enum.
# This ensures the service never constructs an invalid enum string.
SENSOR_TRIGGER_MAP = {
    "accelerometer": "auto_fall",   # accelerometer data → fall detection
    "gyroscope":     "auto_shake",  # gyroscope data    → shake detection
}


def _is_on_cooldown(user_id, cooldown_seconds=None):
    """Return (is_cooling, seconds_remaining) for the user's SOS rate-limit window."""
    if cooldown_seconds is None:
        cooldown_seconds = SOS_COOLDOWN_SECONDS
    if cooldown_seconds <= 0:
        return False, 0
    last_trigger = _sos_cooldown.get(user_id)
    if last_trigger is None:
        return False, 0
    elapsed = time.time() - last_trigger
    if elapsed < cooldown_seconds:
        return True, int(cooldown_seconds - elapsed)
    return False, 0


def _mark_sos_triggered(user_id):
    """Record that an AUTO SOS was just triggered."""
    _sos_cooldown[user_id] = time.time()


def _is_manual_on_cooldown(user_id):
    """Return (is_cooling, seconds_remaining) for the manual SOS double-tap guard."""
    last_trigger = _manual_sos_cooldown.get(user_id)
    if last_trigger is None:
        return False, 0
    elapsed = time.time() - last_trigger
    if elapsed < MANUAL_SOS_COOLDOWN_SECONDS:
        return True, int(MANUAL_SOS_COOLDOWN_SECONDS - elapsed)
    return False, 0


def _mark_manual_sos_triggered(user_id):
    """Record that a MANUAL SOS was just triggered."""
    _manual_sos_cooldown[user_id] = time.time()


def _clear_manual_cooldown(user_id):
    """Clear the manual SOS cooldown for a user.

    Called after a successful cancel so the user (or IoT device) can
    re-trigger immediately without hitting the 20-second double-tap guard.
    """
    _manual_sos_cooldown.pop(user_id, None)


# ---------------------------------------------------------------------------
# Feature extraction (mirrors data_train.py exactly)
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Feature extraction (mirrors data_train.py exactly)
# ---------------------------------------------------------------------------
def extract_features(window, sensor_type):
    """Extract 17 statistical features from a sensor window.
    
    Features:
    - 15 statistical features from (x, y, z)
    - 2 One-Hot encoded features for sensor_type: [is_accel, is_gyro]

    Args:
        window: np.ndarray of shape (N, 3) — N readings of [x, y, z].
        sensor_type: str ('accelerometer' or 'gyroscope')

    Returns:
        np.ndarray of shape (1, 17) ready for model.predict().
    """
    window = np.array(window, dtype=float)
    feats = []
    for i in range(3):
        axis = window[:, i]
        feats += [axis.mean(), axis.std(), axis.max(), axis.min(), np.sum(axis ** 2)]
    
    # One-Hot Encoding for Sensor Type
    if sensor_type == 'accelerometer':
        feats += [1, 0]
    elif sensor_type == 'gyroscope':
        feats += [0, 1]
    else:
        feats += [0, 0] # Unknown
        
    return np.array(feats).reshape(1, -1)


def predict_danger(window_data, sensor_type='accelerometer'):
    """Run the ML model on a sensor window.

    Args:
        window_data: list of [x, y, z] lists.
        sensor_type: str ('accelerometer' or 'gyroscope')

    Returns:
        (prediction, confidence) — prediction is 0 (safe) or 1 (danger).
    """
    model = _get_model()
    if model is None:
        return 0, 0.0

    features = extract_features(window_data, sensor_type)  # shape (1, 17)

    # ---------------------------------------------------------------------------
    # Feature-count compatibility shim
    # ---------------------------------------------------------------------------
    # The model stored in the DB may have been trained before the two one-hot
    # sensor-type columns were added to extract_features() (i.e. trained on 15
    # features).  sklearn raises a hard ValueError when the column count doesn't
    # match n_features_in_.  We detect this at runtime and trim the feature
    # vector to match what the current model actually expects, so old models keep
    # working without requiring an immediate retrain.
    # Once the model is retrained via /protection/train-model (which now calls
    # extract_features() and therefore produces 17 features), this shim becomes
    # a no-op automatically.
    expected_n = getattr(model, 'n_features_in_', None)
    if expected_n is not None and features.shape[1] != expected_n:
        features = features[:, :expected_n]

    # Get probability if the model supports it
    confidence = 0.0
    prediction = 0

    if hasattr(model, 'predict_proba'):
        proba = model.predict_proba(features)[0]
        # proba is [prob_safe, prob_danger]
        confidence = float(proba[1])  # Probability of Danger
        prediction = 1 if confidence > 0.5 else 0
    else:
        prediction = int(model.predict(features)[0])
        confidence = 1.0 if prediction == 1 else 0.0

    return prediction, confidence


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def toggle_protection(user_id, is_active):
    """Toggle Auto SOS on/off for the given user.

    Persists the flag to ``user_settings.auto_sos_enabled`` so the preference
    survives server restarts.  The in-memory ``active_protection_users`` cache
    is updated simultaneously so subsequent requests within the same process
    are still O(1).
    """
    from app.models.settings import UserSettings
    from app.extensions import db

    # Persist to DB
    settings = UserSettings.query.filter_by(user_id=user_id).first()
    if settings:
        settings.auto_sos_enabled = is_active
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"⚠️ Failed to persist protection toggle: {e}")

    # Keep in-memory cache in sync
    if is_active:
        active_protection_users[user_id] = True
        return True, "Auto SOS protection activated"
    else:
        active_protection_users.pop(user_id, None)
        return True, "Auto SOS protection deactivated"


def _is_protection_active(user_id):
    """Return True if Auto SOS is enabled for user_id.

    Checks the fast in-memory cache first.  On cache miss (e.g. after a
    server restart) it falls back to the DB and warms the cache for the
    next call.
    """
    # Fast path
    if active_protection_users.get(user_id):
        return True

    # Slow path: DB look-up (only once per user per process lifetime)
    try:
        from app.models.settings import UserSettings
        settings = UserSettings.query.filter_by(user_id=user_id).first()
        if settings and settings.auto_sos_enabled:
            active_protection_users[user_id] = True  # warm cache
            return True
    except Exception:
        pass

    return False


def get_protection_status(user_id):
    is_active = _is_protection_active(user_id)
    
    # Check for connected bracelet
    from app.models.device import ConnectedDevice
    device = ConnectedDevice.query.filter_by(user_id=user_id, is_connected=True).first()
    bracelet_connected = (device is not None)

    return {
        "is_active": is_active,
        "bracelet_connected": bracelet_connected
    }


def analyze_sensor_data(user_id, sensor_type, readings, sensitivity):
    """Analyze incoming sensor readings using the ML model.

    This uses probability thresholds based on sensitivity.
    High Sensitivity -> Trigger on lower confidence (e.g., > 30%)
    Low Sensitivity -> Trigger only on high confidence (e.g., > 80%)
    """
    if not _is_protection_active(user_id):
        return {"alert_triggered": False, "confidence": 0.0}

    # Convert [{x, y, z, timestamp}, ...] into [[x, y, z], ...]
    window_data = [[r['x'], r['y'], r['z']] for r in readings]

    # Predict
    # strict_prediction is just based on 0.5 cutoff, but we use confidence for sensitivity
    strict_prediction, confidence_danger = predict_danger(window_data, sensor_type)

    # Sensitivity Thresholds
    # Lower threshold = Easier to trigger (Higher sensitivity)
    thresholds = {
        "high": 0.35,   # Trigger if > 35% chance of danger
        "medium": 0.60, # Trigger if > 60% chance
        "low": 0.85     # Trigger if > 85% chance
    }
    
    threshold = thresholds.get(sensitivity.lower(), 0.60)
    is_danger = confidence_danger >= threshold

    # -------------------------------------------------------
    # AUTO-LABELING (Save data for retraining)
    # -------------------------------------------------------
    # We allow the model to learn from its own decisions (Self-Training Loop)
    # Ideally, user would verify this (True Positive/False Positive).
    # ensure we don't block the thread
    try:
        # Determine label: 1 if we think it's danger, 0 otherwise
        predicted_label = 1 if is_danger else 0
        save_training_data(user_id, sensor_type, readings, label=predicted_label, is_verified=False)
    except Exception as e:
        print(f"⚠️ Failed to auto-save training data: {e}")

    if is_danger:
        # Check cooldown before triggering SOS
        on_cooldown, secs_left = _is_on_cooldown(user_id)
        if on_cooldown:
            mins_left = (secs_left + 59) // 60
            return {
                "alert_triggered": False,
                "confidence": confidence_danger,
                "message": f"Auto SOS rate-limited. Next trigger allowed in {mins_left} min.",
                "retry_after_seconds": secs_left
            }

        # Trigger SOS
        from app.services.location_service import get_last_location
        last_loc = get_last_location(user_id)
        lat = last_loc.latitude if last_loc else 0.0
        lng = last_loc.longitude if last_loc else 0.0

        trigger_type = SENSOR_TRIGGER_MAP.get(sensor_type, "auto_fall")
        alert, msg = trigger_sos(user_id, lat, lng, trigger_type=trigger_type)
        _mark_sos_triggered(user_id)

        # Send WhatsApp alert (sync so we can capture sandbox errors)
        try:
            from app.services.whatsapp_service import send_whatsapp_sync
            from app.models.trusted_contact import TrustedContact
            contacts = TrustedContact.query.filter_by(user_id=user_id).all()
            maps_link = f"https://maps.google.com/?q={lat},{lng}"
            whatsapp_msg = f"⚠ SOS ALERT!\nDanger detected via {sensor_type}!\nConfidence: {int(confidence_danger*100)}%\n📍 Location: {maps_link}"
            delivery_report = []
            for contact in contacts:
                result = send_whatsapp_sync(contact.phone, whatsapp_msg)
                delivery_report.append({"phone": contact.phone, **result})
                if not result["success"]:
                    current_app.logger.warning(
                        f"Auto SOS WhatsApp failed for {contact.phone} "
                        f"[{result['status']}] code={result['error_code']}: {result['error_msg']}"
                    )
        except Exception as e:
            current_app.logger.error(f"WhatsApp alert failed: {e}")
            delivery_report = []

        return {
            "alert_triggered": True,
            "alert_id": alert.id if alert else None,
            "confidence": confidence_danger,
            "delivery_report": delivery_report
        }

    return {"alert_triggered": False, "confidence": confidence_danger}


def predict_from_window(user_id, window_data, sensor_type='accelerometer', location="Unknown", latitude=None, longitude=None):
    """Direct window-based prediction for the Auto SOS pipeline.

    Called by the frontend **after** the local threshold check fires —
    i.e. the raw sensor magnitude already exceeded the user-configured
    threshold on-device.  This function runs the ML model and, if danger
    is predicted, starts an SOS countdown.

    Args:
        user_id: The authenticated user's ID.
        window_data: list of [x, y, z] lists (pre-filtered by the client).
        sensor_type: 'accelerometer' or 'gyroscope' — determines trigger label.
        location: Optional human-readable location string.
        latitude: GPS latitude from the device (preferred over DB fallback).
        longitude: GPS longitude from the device (preferred over DB fallback).

    Returns:
        dict with prediction result and SOS status.
    """
    # Guard: only process if Auto SOS is toggled on
    if not _is_protection_active(user_id):
        return {
            "prediction": 0,
            "confidence": 0.0,
            "sos_sent": False,
            "message": "Auto SOS is not enabled. Toggle it on first."
        }

    prediction, confidence = predict_danger(window_data, sensor_type)

    response = {"prediction": prediction, "confidence": confidence, "sensor_type": sensor_type}

    if prediction == 1:
        # Check cooldown
        on_cooldown, secs_left = _is_on_cooldown(user_id)
        if on_cooldown:
            mins_left = (secs_left + 59) // 60
            response["sos_sent"] = False
            response["message"] = f"Auto SOS rate-limited. Next trigger allowed in {mins_left} min."
            response["retry_after_seconds"] = secs_left
            return response

        # Resolve coordinates: prefer device-supplied GPS, fall back to DB
        if latitude is not None and longitude is not None:
            lat, lng = latitude, longitude
        else:
            from app.services.location_service import get_last_location
            last_loc = get_last_location(user_id)
            lat = last_loc.latitude if last_loc else 0.0
            lng = last_loc.longitude if last_loc else 0.0

        trigger_type = SENSOR_TRIGGER_MAP.get(sensor_type, "auto_fall")
        alert, msg = trigger_sos(user_id, lat, lng, trigger_type=trigger_type)
        _mark_sos_triggered(user_id)

        # Send WhatsApp alert (sync so we can capture sandbox errors)
        try:
            from app.services.whatsapp_service import send_whatsapp_sync
            from app.models.trusted_contact import TrustedContact
            contacts = TrustedContact.query.filter_by(user_id=user_id).all()
            maps_link = f"https://maps.google.com/?q={lat},{lng}"
            whatsapp_msg = (
                f"⚠ SOS ALERT!\nDanger detected via {sensor_type}!\n"
                f"Confidence: {int(confidence*100)}%\n"
                f"📍 Location: {location}\n🗺 Map: {maps_link}"
            )
            delivery_report = []
            for contact in contacts:
                result = send_whatsapp_sync(contact.phone, whatsapp_msg)
                delivery_report.append({"phone": contact.phone, **result})
                if not result["success"]:
                    current_app.logger.warning(
                        f"Auto SOS WhatsApp failed for {contact.phone} "
                        f"[{result['status']}] code={result['error_code']}: {result['error_msg']}"
                    )
        except Exception as e:
            current_app.logger.error(f"WhatsApp alert failed: {e}")
            delivery_report = []

        response["sos_sent"] = True
        response["alert_id"] = alert.id if alert else None
        response["message"] = msg
        response["delivery_report"] = delivery_report

    else:
        response["sos_sent"] = False

    return response


# ---------------------------------------------------------------------------
# Data Collection / RL
# ---------------------------------------------------------------------------
def save_training_data(user_id, sensor_type, readings, label, is_verified=False):
    """Save raw sensor data for future model training.
    
    Args:
        user_id: User ID
        sensor_type: 'accelerometer' or 'gyroscope'
        readings: List of {x, y, z, timestamp}
        label: 0 (Safe) or 1 (Danger)
        is_verified: boolean, true if manually corrected by user
    """
    from app.models.sensor_data import SensorTrainingData
    from app.extensions import db
    
    try:
        new_records = []
        for r in readings:
            record = SensorTrainingData(
                user_id=user_id,
                sensor_type=sensor_type,
                timestamp=r['timestamp'],
                x=r['x'],
                y=r['y'],
                z=r['z'],
                label=label,
                is_verified=is_verified
            )
            new_records.append(record)
        
        db.session.add_all(new_records)
        db.session.commit()
        return True, f"Saved {len(new_records)} training records."
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to save training data: {e}")
        return False, str(e)


def submit_sos_feedback(user_id, alert_id, is_false_alarm):
    """Record user feedback after an Auto SOS event.

    When the user confirms the SOS was a false alarm (``is_false_alarm=True``)
    or a genuine danger (``is_false_alarm=False``), we re-label the sensor data
    that was captured around that alert so the ML model can learn from the
    correction on the next training run.

    Args:
        user_id:        Authenticated user ID.
        alert_id:       SOSAlert UUID that the feedback refers to.
        is_false_alarm: True  → user says it was NOT danger (label 0).
                        False → user confirms it WAS danger (label 1).

    Returns:
        (success: bool, message: str)
    """
    from app.models.sos_alert import SOSAlert
    from app.models.sensor_data import SensorTrainingData
    from app.extensions import db

    alert = SOSAlert.query.filter_by(id=alert_id, user_id=user_id).first()
    if not alert:
        return False, "Alert not found or does not belong to you"

    # Determine the correct label from feedback
    correct_label = 0 if is_false_alarm else 1

    try:
        # Find the unverified sensor records captured around this alert's timestamp
        from datetime import timedelta
        window_start = alert.triggered_at - timedelta(seconds=5)
        window_end   = alert.triggered_at + timedelta(seconds=5)

        records = SensorTrainingData.query.filter(
            SensorTrainingData.user_id == user_id,
            SensorTrainingData.is_verified == False,  # noqa: E712
            SensorTrainingData.created_at.between(window_start, window_end)
        ).all()

        updated = 0
        for record in records:
            record.label = correct_label
            record.is_verified = True
            updated += 1

        # If the alert was a false alarm and it's still in countdown, cancel it
        if is_false_alarm and alert.status == 'countdown':
            alert.status = 'cancelled'
            from datetime import datetime
            alert.resolved_at = datetime.utcnow()
            alert.resolution_type = 'false_alarm'

        db.session.commit()
        return True, f"Feedback saved — {updated} training record(s) re-labelled as {'safe' if is_false_alarm else 'danger'}."
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to save SOS feedback: {e}")
        return False, str(e)
