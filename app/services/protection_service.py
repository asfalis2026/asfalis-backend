
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

# SOS cooldown tracker: user_id -> last SOS trigger timestamp
_sos_cooldown = {}
SOS_COOLDOWN_SECONDS = 20


def _is_on_cooldown(user_id):
    """Return True if the user has triggered an SOS within the last 20 seconds."""
    last_trigger = _sos_cooldown.get(user_id)
    if last_trigger is None:
        return False
    return (time.time() - last_trigger) < SOS_COOLDOWN_SECONDS


def _mark_sos_triggered(user_id):
    """Record that an SOS was just triggered for cooldown tracking."""
    _sos_cooldown[user_id] = time.time()


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

    features = extract_features(window_data, sensor_type)
    
    # Get probability if the model supports it
    confidence = 0.0
    prediction = 0
    
    if hasattr(model, 'predict_proba'):
        proba = model.predict_proba(features)[0]
        # proba is [prob_safe, prob_danger]
        confidence = float(proba[1]) # Probability of Danger
        # We don't use model.predict() here, we use threshold logic in analyze_sensor_data
        # But for backward compatibility, let's say:
        prediction = 1 if confidence > 0.5 else 0
    else:
        prediction = int(model.predict(features)[0])
        confidence = 1.0 if prediction == 1 else 0.0

    return prediction, confidence


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def toggle_protection(user_id, is_active):
    if is_active:
        active_protection_users[user_id] = True
        return True, "Protection activated"
    else:
        active_protection_users.pop(user_id, None)
        return True, "Protection deactivated"


def get_protection_status(user_id):
    is_active = active_protection_users.get(user_id, False)
    
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
    if not active_protection_users.get(user_id):
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
        if _is_on_cooldown(user_id):
            return {
                "alert_triggered": False,
                "confidence": confidence_danger,
                "message": "SOS on cooldown, please wait before triggering again."
            }

        # Trigger SOS
        from app.services.location_service import get_last_location
        last_loc = get_last_location(user_id)
        lat = last_loc.latitude if last_loc else 0.0
        lng = last_loc.longitude if last_loc else 0.0

        alert, msg = trigger_sos(user_id, lat, lng, trigger_type=f"auto_{sensor_type}")
        _mark_sos_triggered(user_id)

        # Send WhatsApp alert
        try:
            from app.services.whatsapp_service import send_whatsapp_alert
            from app.models.trusted_contact import TrustedContact
            contacts = TrustedContact.query.filter_by(user_id=user_id).all()
            maps_link = f"https://maps.google.com/?q={lat},{lng}"
            whatsapp_msg = f"⚠ SOS ALERT!\nDanger detected via {sensor_type}!\nConfidence: {int(confidence_danger*100)}%\n📍 Location: {maps_link}"
            for contact in contacts:
                send_whatsapp_alert(contact.phone, whatsapp_msg)
        except Exception as e:
            current_app.logger.error(f"WhatsApp alert failed: {e}")

        return {
            "alert_triggered": True,
            "alert_id": alert.id if alert else None,
            "confidence": confidence_danger
        }

    return {"alert_triggered": False, "confidence": confidence_danger}


def predict_from_window(user_id, window_data, location="Unknown"):
    """Direct window-based prediction (mirrors dummy_server.py /predict).

    Args:
        user_id: The authenticated user's ID.
        window_data: list of [x, y, z] lists.
        location: Optional location string.

    Returns:
        dict with prediction result.
    """
    prediction, confidence = predict_danger(window_data)

    response = {"prediction": prediction, "confidence": confidence}

    if prediction == 1:
        # Check cooldown
        if _is_on_cooldown(user_id):
            response["sos_sent"] = False
            response["message"] = "SOS on cooldown, please wait before triggering again."
            return response

        # Trigger SOS
        from app.services.location_service import get_last_location
        last_loc = get_last_location(user_id)
        lat = last_loc.latitude if last_loc else 0.0
        lng = last_loc.longitude if last_loc else 0.0

        alert, msg = trigger_sos(user_id, lat, lng, trigger_type="auto_sensor_window")
        _mark_sos_triggered(user_id)

        # Send WhatsApp alert
        try:
            from app.services.whatsapp_service import send_whatsapp_alert
            from app.models.trusted_contact import TrustedContact
            contacts = TrustedContact.query.filter_by(user_id=user_id).all()
            maps_link = f"https://maps.google.com/?q={lat},{lng}"
            whatsapp_msg = f"⚠ SOS ALERT!\nDanger detected!\n📍 Location: {location}\n🗺 Map: {maps_link}"
            for contact in contacts:
                send_whatsapp_alert(contact.phone, whatsapp_msg)
        except Exception as e:
            current_app.logger.error(f"WhatsApp alert failed: {e}")

        response["sos_sent"] = True
        response["alert_id"] = alert.id if alert else None

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
