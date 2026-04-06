import os
import time
import numpy as np
import joblib
import logging
import io
from app.config import settings
from app.extensions import db
from app.models.ml_model import MLModel
from app.models.sensor_data import SensorTrainingData
from sklearn.preprocessing import StandardScaler
try:
    import lightgbm as lgb
except Exception as e:
    logging.warning(f"⚠️ LightGBM could not be imported: {e}. Auto-SOS predictions will be disabled.")
    lgb = None

from app.services.sos_service import trigger_sos

# ---------------------------------------------------------------------------
# Model loading (once at import time)
# ---------------------------------------------------------------------------
_MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'auto_sos_model_LightGBM.pkl')
_SCALER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'auto_sos_scaler.pkl')
_model = None
_scaler = None
_model_db_id = None  # DB row ID of the loaded model; None = file fallback / not loaded yet

def _load_scaler():
    """Lazy-load the StandardScaler used for feature normalization."""
    global _scaler
    if _scaler is None:
        if os.path.exists(_SCALER_PATH):
            _scaler = joblib.load(_SCALER_PATH)
            print(f"✅ Loaded scaler from {_SCALER_PATH}")
        else:
            print(f"⚠️ Scaler file not found at {_SCALER_PATH} — features will NOT be scaled.")
    return _scaler


def _get_model():
    """Lazy-load the ML model from the Database (or fallback to file).

    Tracks the active DB model row ID so the cache is automatically
    invalidated when a new model is trained.  Call ``_reset_model_cache()``
    after training to force an immediate reload on the next request.
    """
    global _model, _model_db_id
    if _model is None:
        try:
            # Try loading from DB first
            from app.models.ml_model import MLModel
            import io

            active_model = MLModel.query.filter_by(is_active=True).order_by(MLModel.created_at.desc()).first()

            if active_model:
                with io.BytesIO(active_model.data) as f:
                    _model = joblib.load(f)
                _model_db_id = active_model.id
                print(f"✅ Loaded ML model {active_model.version} from DB (id={active_model.id})")
                # Also load the scaler
                _load_scaler()
                return _model

            # Fallback to file if no DB model (not yet calibrated)
            if os.path.exists(_MODEL_PATH):
                _model = joblib.load(_MODEL_PATH)
                _model_db_id = None  # Signals "file-based / uncalibrated"
                print(f"⚠️ Loaded fallback model from {_MODEL_PATH}")
            else:
                print("❌ No active model found in DB or file.")

            # Load the scaler regardless of model source
            _load_scaler()

        except Exception as e:
            print(f"❌ Failed to load model: {e}")

    return _model


def _reset_model_cache():
    """Invalidate the in-process ML model cache.

    Must be called after a new model is successfully saved to the DB so that
    the next prediction request loads the freshly calibrated model instead of
    the stale cached one.  Without this, a running server process would keep
    using the old model until it is restarted.
    """
    global _model, _scaler, _model_db_id
    _model = None
    _scaler = None
    _model_db_id = None
    print("🔄 ML model cache invalidated — will reload from DB on next prediction.")


def _has_db_model():
    """Return True if the currently cached model came from the DB.

    Used to block auto-SOS triggers when only the uncalibrated file-fallback
    model is loaded.  A file-based model was not trained on the user's sensor
    data and will produce unreliable predictions, especially during or just
    after device calibration.
    """
    # Force a load attempt so the flag is accurate even on the first call.
    _get_model()
    return _model_db_id is not None


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
def extract_features(window):
    """Extract 39 statistical features from a 300-reading sensor window.

    The feature set matches the ``labeled_windows.csv`` schema produced by the
    ML data pipeline and is the canonical representation used for both model
    training (``retrain_model``) and inference (``predict_danger``).

    Features (39 total):
      Per-axis (x, y, z): mean, std, min, max, range, median, iqr, rms  → 24
      Magnitude:          mean, std, min, max, range, median, iqr, rms  →  8
      Cross-correlations: xy_corr, xz_corr, yz_corr                    →  3

    Args:
        window: array-like of shape (N, 3) — N readings of [x, y, z].

    Returns:
        np.ndarray of shape (1, 39) ready for model.predict().
        dict of named features (for DB persistence).
    """
    window = np.array(window, dtype=float)
    if window.ndim != 2 or window.shape[1] != 3:
        raise ValueError(
            f"extract_features expects window shape (N, 3), got {window.shape}. "
            "Each reading must be [x, y, z]."
        )

    x, y, z = window[:, 0], window[:, 1], window[:, 2]
    mag = np.sqrt(x ** 2 + y ** 2 + z ** 2)

    def _axis_stats(a):
        q75, q25 = np.percentile(a, [75, 25])
        return [
            float(a.mean()),
            float(a.std()),
            float(a.min()),
            float(a.max()),
            float(a.max() - a.min()),   # range
            float(np.median(a)),
            float(q75 - q25),           # IQR
            float(np.sqrt(np.mean(a ** 2))),  # RMS
        ]

    xs  = _axis_stats(x)
    ys  = _axis_stats(y)
    zs  = _axis_stats(z)
    ms  = _axis_stats(mag)

    # Pearson correlations (clip to [-1, 1] to guard against NaN on constant axes)
    def _safe_corr(a, b):
        if a.std() == 0 or b.std() == 0:
            return 0.0
        return float(np.corrcoef(a, b)[0, 1])

    xy_corr = _safe_corr(x, y)
    xz_corr = _safe_corr(x, z)
    yz_corr = _safe_corr(y, z)

    feature_vector = np.array(xs + ys + zs + ms + [xy_corr, xz_corr, yz_corr]).reshape(1, -1)

    # Named dict for DB persistence (matches SensorTrainingData columns exactly)
    named = {
        'x_mean':   xs[0], 'x_std':    xs[1], 'x_min':    xs[2], 'x_max':    xs[3],
        'x_range':  xs[4], 'x_median': xs[5], 'x_iqr':    xs[6], 'x_rms':    xs[7],
        'y_mean':   ys[0], 'y_std':    ys[1], 'y_min':    ys[2], 'y_max':    ys[3],
        'y_range':  ys[4], 'y_median': ys[5], 'y_iqr':    ys[6], 'y_rms':    ys[7],
        'z_mean':   zs[0], 'z_std':    zs[1], 'z_min':    zs[2], 'z_max':    zs[3],
        'z_range':  zs[4], 'z_median': zs[5], 'z_iqr':    zs[6], 'z_rms':    zs[7],
        'mag_mean': ms[0], 'mag_std':  ms[1], 'mag_min':  ms[2], 'mag_max':  ms[3],
        'mag_range':ms[4], 'mag_median':ms[5],'mag_iqr':  ms[6], 'mag_rms':  ms[7],
        'xy_corr': xy_corr, 'xz_corr': xz_corr, 'yz_corr': yz_corr,
    }

    return feature_vector, named


def predict_danger(window_data):
    """Run the ML model on a sensor window.

    Args:
        window_data: list of [x, y, z] lists (300 readings).

    Returns:
        (prediction, confidence) — prediction is 0 (safe) or 1 (danger).
    """
    model = _get_model()
    if model is None:
        return 0, 0.0

    features, _ = extract_features(window_data)  # shape (1, 39)

    # -----------------------------------------------------------------------
    # Feature-count shim: old models (17 features) still work until retrained
    # -----------------------------------------------------------------------
    expected_n = getattr(model, 'n_features_in_', None)
    if expected_n is not None and features.shape[1] != expected_n:
        features = features[:, :expected_n]

    # -----------------------------------------------------------------------
    # Apply StandardScaler normalization (required by LightGBM model)
    # -----------------------------------------------------------------------
    scaler = _load_scaler()
    if scaler is not None:
        try:
            features = scaler.transform(features)
        except Exception:
            pass  # If scaler and feature dims mismatch, proceed unscaled

    confidence = 0.0
    prediction = 0

    if hasattr(model, 'predict_proba'):
        proba = model.predict_proba(features)[0]
        confidence = float(proba[1])  # P(danger)
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
    is updated **only after** the DB write succeeds, so the process state
    and the DB state cannot diverge (which would cause false-armed behaviour
    after a restart).
    """
    from app.models.settings import UserSettings
    # from app.extensions import db # Already imported at top

    # Create the settings row if it doesn't exist yet (e.g. fresh account).
    settings_obj = UserSettings.query.filter_by(user_id=user_id).first()
    if not settings_obj:
        settings_obj = UserSettings(user_id=user_id)
        db.session.add(settings_obj)

    settings_obj.auto_sos_enabled = is_active
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        # Do NOT update the in-memory cache when the DB write fails.
        # Leaving the cache unchanged keeps it consistent with the DB so the
        # protection state is predictable after a server restart.
        return False, f"Failed to update protection state: {e}"

    # Cache update only reaches here on DB success.
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
        settings_obj = UserSettings.query.filter_by(user_id=user_id).first()
        if settings_obj and settings_obj.auto_sos_enabled:
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

    Flow 2 (Auto SOS):
      1. Extract features from the 300-reading window.
      2. Run ML inference with sensitivity-based threshold.
      3. If DANGER → start 10-second countdown (DO NOT dispatch immediately).
      4. Send FCM push so the app shows the cancel UI regardless of state.
      5. Auto-save the window as training data for future retraining.
      6. Return alert_id + countdown_seconds to the app.

    The app is responsible for calling /sos/send-now when the timer expires
    without a cancel, or /sos/cancel if the user dismisses the alert.

    Sensitivity thresholds:
      high   → trigger at > 35% danger probability
      medium → trigger at > 60%
      low    → trigger at > 85%
    """
    if not _is_protection_active(user_id):
        return {"alert_triggered": False, "confidence": 0.0}

    # Convert [{x, y, z, timestamp}, ...] into [[x, y, z], ...]
    window_data = [[r['x'], r['y'], r['z']] for r in readings]

    strict_prediction, confidence_danger = predict_danger(window_data)

    thresholds = {
        "high":   0.35,
        "medium": 0.60,
        "low":    0.85,
    }
    threshold = thresholds.get(sensitivity.lower(), 0.60)
    is_danger = confidence_danger >= threshold

    # -------------------------------------------------------
    # AUTO-LABELING — persist window features for retraining
    # -------------------------------------------------------
    try:
        predicted_label = 1 if is_danger else 0
        save_training_data(user_id, window_data, label=predicted_label, is_verified=False)
    except Exception as e:
        logging.warning(f"⚠️ Failed to auto-save training data: {e}")

    if is_danger:
        # Block until a calibrated DB model is available
        if not _has_db_model():
            logging.warning(
                f"Auto SOS blocked for user {user_id}: no calibrated DB model."
            )
            return {
                "alert_triggered": False,
                "confidence": confidence_danger,
                "message": "Auto SOS suspended: model not calibrated. Complete calibration first.",
                "trigger_reason": "model_not_calibrated",
            }

        # Race-condition guard: user may have disarmed between cache check and now
        from app.models.settings import UserSettings
        fresh_settings = UserSettings.query.filter_by(user_id=user_id).first()
        if not (fresh_settings and fresh_settings.auto_sos_enabled):
            logging.info(f"Auto SOS suppressed for user {user_id}: system disarmed.")
            return {
                "alert_triggered": False,
                "confidence": confidence_danger,
                "message": "Auto SOS suppressed: system is disarmed.",
            }

        on_cooldown, secs_left = _is_on_cooldown(user_id)
        if on_cooldown:
            mins_left = (secs_left + 59) // 60
            return {
                "alert_triggered": False,
                "confidence": confidence_danger,
                "message": f"Auto SOS rate-limited. Next trigger allowed in {mins_left} min.",
                "retry_after_seconds": secs_left,
            }

        from app.services.location_service import get_last_location
        last_loc = get_last_location(user_id)
        lat = last_loc.latitude if last_loc else 0.0
        lng = last_loc.longitude if last_loc else 0.0

        trigger_type = SENSOR_TRIGGER_MAP.get(sensor_type, "auto_fall")
        trigger_reason = (
            "Unusual fall detected" if sensor_type == "accelerometer"
            else "Unusual shake/motion detected"
        )
        trigger_prefix = (
            f"⚠️ AUTO-SOS: {trigger_reason} ({int(confidence_danger * 100)}% confidence)\n"
            f"Sensor: {sensor_type} | System was armed at time of trigger"
        )
        alert, msg, countdown_seconds = trigger_sos(
            user_id, lat, lng,
            trigger_type=trigger_type,
            trigger_prefix=trigger_prefix,
            trigger_reason=trigger_reason,
        )
        _mark_sos_triggered(user_id)

        logging.warning(
            f"Auto SOS countdown started for user {user_id}: {trigger_reason} "
            f"confidence={confidence_danger:.2f} sensor={sensor_type}"
        )

        # -------------------------------------------------------------------
        # FCM push — lets app surface cancel UI even when backgrounded
        # -------------------------------------------------------------------
        if alert:
            try:
                from app.services.fcm_service import send_push_notification
                from app.models.user import User
                user = db.session.get(User, user_id)
                if user and user.fcm_token:
                    send_push_notification(
                        fcm_token=user.fcm_token,
                        title="⚠️ Auto SOS Triggered",
                        body=f"{trigger_reason} — tap to cancel within {countdown_seconds}s",
                        data={
                            "type":             "AUTO_SOS_COUNTDOWN",
                            "alert_id":         str(alert.id),
                            "countdown_seconds": str(countdown_seconds),
                        },
                    )
            except Exception as fcm_err:
                logging.warning(f"FCM push failed (non-fatal): {fcm_err}")

        # ⚠️  DO NOT call dispatch_sos() here.
        # The app receives alert_id + countdown_seconds, shows the cancel UI,
        # and calls POST /sos/send-now if the countdown elapses without cancel.
        return {
            "alert_triggered":   True,
            "alert_id":          alert.id if alert else None,
            "confidence":        confidence_danger,
            "trigger_reason":    trigger_reason,
            "countdown_seconds": countdown_seconds,
        }

    return {"alert_triggered": False, "confidence": confidence_danger}


def predict_from_window(user_id, window_data, sensor_type='accelerometer', location="Unknown", latitude=None, longitude=None):
    """Direct window-based prediction for the Auto SOS pipeline.

    Called by the app after its local threshold check fires (magnitude
    exceeded user-configured threshold on-device). Runs ML inference and,
    if DANGER is predicted, starts the 10-second cancellation countdown.
    An FCM push is sent so the app can show the cancel UI even when
    backgrounded.

    The app MUST call POST /sos/send-now if the countdown elapses without
    a cancel, or POST /sos/cancel if the user dismisses the alert.

    Args:
        user_id:     Authenticated user's ID.
        window_data: [[x, y, z], ...] — 300 readings pre-filtered by client.
        sensor_type: 'accelerometer' | 'gyroscope' — determines trigger label.
        location:    Optional human-readable location string.
        latitude:    GPS latitude from device (preferred over DB fallback).
        longitude:   GPS longitude from device (preferred over DB fallback).

    Returns:
        dict with prediction result and SOS countdown status.
    """
    if not _is_protection_active(user_id):
        return {
            "prediction": 0,
            "confidence": 0.0,
            "sos_sent": False,
            "message": "Auto SOS is not enabled. Toggle it on first.",
        }

    prediction, confidence = predict_danger(window_data)

    response = {"prediction": prediction, "confidence": confidence, "sensor_type": sensor_type}

    if prediction == 1:
        if not _has_db_model():
            logging.warning(f"Auto SOS (predict) blocked for user {user_id}: no calibrated DB model.")
            response["sos_sent"] = False
            response["message"] = "Auto SOS suspended: model not calibrated. Complete calibration first."
            response["trigger_reason"] = "model_not_calibrated"
            return response

        from app.models.settings import UserSettings
        fresh_settings = UserSettings.query.filter_by(user_id=user_id).first()
        if not (fresh_settings and fresh_settings.auto_sos_enabled):
            logging.info(f"Auto SOS (predict) suppressed for user {user_id}: system disarmed.")
            response["sos_sent"] = False
            response["message"] = "Auto SOS suppressed: system is disarmed."
            return response

        on_cooldown, secs_left = _is_on_cooldown(user_id)
        if on_cooldown:
            mins_left = (secs_left + 59) // 60
            response["sos_sent"] = False
            response["message"] = f"Auto SOS rate-limited. Next trigger allowed in {mins_left} min."
            response["retry_after_seconds"] = secs_left
            return response

        if latitude is not None and longitude is not None:
            lat, lng = latitude, longitude
        else:
            from app.services.location_service import get_last_location
            last_loc = get_last_location(user_id)
            lat = last_loc.latitude if last_loc else 0.0
            lng = last_loc.longitude if last_loc else 0.0

        trigger_type = SENSOR_TRIGGER_MAP.get(sensor_type, "auto_fall")
        trigger_reason = (
            "Unusual fall detected" if sensor_type == "accelerometer"
            else "Unusual shake/motion detected"
        )
        trigger_prefix = (
            f"⚠️ AUTO-SOS: {trigger_reason} ({int(confidence * 100)}% confidence)\n"
            f"Sensor: {sensor_type} | Location: {location} | System was armed"
        )
        alert, msg, countdown_seconds = trigger_sos(
            user_id, lat, lng,
            trigger_type=trigger_type,
            trigger_prefix=trigger_prefix,
            trigger_reason=trigger_reason,
        )
        _mark_sos_triggered(user_id)

        logging.warning(
            f"Auto SOS (predict) countdown started for user {user_id}: "
            f"{trigger_reason} confidence={confidence:.2f} sensor={sensor_type}"
        )

        # -------------------------------------------------------------------
        # FCM push — ensures app surfaces cancel UI when backgrounded
        # -------------------------------------------------------------------
        if alert:
            try:
                from app.services.fcm_service import send_push_notification
                from app.models.user import User
                user = db.session.get(User, user_id)
                if user and user.fcm_token:
                    send_push_notification(
                        fcm_token=user.fcm_token,
                        title="⚠️ Auto SOS Triggered",
                        body=f"{trigger_reason} — tap to cancel within {countdown_seconds}s",
                        data={
                            "type":             "AUTO_SOS_COUNTDOWN",
                            "alert_id":         str(alert.id),
                            "countdown_seconds": str(countdown_seconds),
                        },
                    )
            except Exception as fcm_err:
                logging.warning(f"FCM push failed (non-fatal): {fcm_err}")

        response["sos_sent"] = True
        response["alert_id"] = alert.id if alert else None
        response["message"] = msg
        response["trigger_reason"] = trigger_reason
        response["countdown_seconds"] = countdown_seconds

    else:
        response["sos_sent"] = False

    return response


# ---------------------------------------------------------------------------
# Data Collection / RL
# ---------------------------------------------------------------------------
def save_training_data(
    user_id,
    window_data,
    label,
    is_verified=False,
    dataset_name=None,
    motion_description=None,
    sos_alert_id=None,
):
    """Extract features from a sensor window and persist one training row.

    Each call stores exactly **one** ``SensorTrainingData`` row representing
    the 39 statistical features of the full window.  This replaces the old
    per-reading approach and aligns with the ``labeled_windows.csv`` schema.

    Args:
        user_id:           Authenticated user ID.
        window_data:       list of [x, y, z] triplets (ideally 300 readings).
        label:             0 = SAFE, 1 = DANGER.
        is_verified:       True if the label was confirmed by the user.
        dataset_name:      Optional motion category tag (e.g. 'fast_walking').
        motion_description: Optional free-text description.
        sos_alert_id:      Optional SOSAlert UUID — links the window to the
                           alert that triggered / confirmed it.

    Returns:
        (success: bool, message: str)
    """
    from app.models.sensor_data import SensorTrainingData
    from app.extensions import db

    try:
        _, named = extract_features(window_data)

        record = SensorTrainingData(
            user_id=user_id,
            danger_label=int(label),
            is_verified=is_verified,
            dataset_name=dataset_name,
            motion_description=motion_description,
            sos_alert_id=sos_alert_id,
            **named,
        )
        db.session.add(record)
        db.session.commit()
        return True, "Saved 1 window-level training record."
    except Exception as e:
        db.session.rollback()
        logging.error(f"Failed to save training data: {e}")
        return False, str(e)


def submit_sos_feedback(user_id, alert_id, is_false_alarm):
    """Record user feedback after an Auto SOS event.

    Finds the ``SensorTrainingData`` window row linked to this alert via
    ``sos_alert_id`` and updates its label so the ML model learns from the
    user's correction on the next training run.

    Flow 2 (Cancel path):
      - ``is_false_alarm=True``  → re-label the window as SAFE (0)
      - ``is_false_alarm=False`` → confirm as DANGER (1)

    Args:
        user_id:        Authenticated user ID.
        alert_id:       SOSAlert UUID that the feedback refers to.
        is_false_alarm: True → NOT danger (label 0); False → IS danger (label 1).

    Returns:
        (success: bool, message: str)
    """
    from app.models.sos_alert import SOSAlert
    from app.models.sensor_data import SensorTrainingData
    from app.extensions import db

    alert = SOSAlert.query.filter_by(id=alert_id, user_id=user_id).first()
    if not alert:
        return False, "Alert not found or does not belong to you"

    correct_label = 0 if is_false_alarm else 1
    label_text = 'safe' if is_false_alarm else 'danger'

    try:
        # Primary: find the window row directly linked to this alert
        record = SensorTrainingData.query.filter_by(
            sos_alert_id=alert_id,
            user_id=user_id,
        ).first()

        if record:
            record.danger_label = correct_label
            record.is_verified = True
            updated = 1
        else:
            # Fallback: match by timestamp proximity (±5s) for windows that
            # were saved before sos_alert_id linkage was implemented
            from datetime import timedelta
            window_start = alert.triggered_at - timedelta(seconds=5)
            window_end   = alert.triggered_at + timedelta(seconds=5)
            records = SensorTrainingData.query.filter(
                SensorTrainingData.user_id == user_id,
                SensorTrainingData.is_verified == False,  # noqa: E712
                SensorTrainingData.created_at.between(window_start, window_end)
            ).all()
            updated = 0
            for r in records:
                r.danger_label = correct_label
                r.is_verified = True
                updated += 1

        # If the alert was a false alarm and still counting down, cancel it
        if is_false_alarm and alert.status == 'countdown':
            alert.status = 'cancelled'
            from datetime import datetime
            alert.resolved_at = datetime.utcnow()
            alert.resolution_type = 'false_alarm'

        db.session.commit()
        return True, f"Feedback saved — {updated} window record(s) re-labelled as {label_text}."
    except Exception as e:
        db.session.rollback()
        logging.error(f"Failed to save SOS feedback: {e}")
        return False, str(e)


def retrain_model(user_id):
    """Retrain the ML model using verified window-level feature rows.

    Each ``SensorTrainingData`` row already contains the 39 pre-extracted
    statistical features (matching ``labeled_windows.csv``), so no windowing
    or feature extraction is needed here — just load, filter, and train.

    Steps:
      1. Fetch all is_verified=True rows from sensor_training_data.
      2. Build X (feature matrix) and y (labels) directly from the rows.
      3. Train a LightGBM classifier.
      4. Persist the trained model to the MLModel table.
    """
    if lgb is None:
        return False, "LightGBM not installed — cannot retrain model."

    try:
        records = SensorTrainingData.query.filter_by(is_verified=True).all()
        if not records:
            return False, "No verified training data found. Collect labelled windows first."

        # Each record exposes its 39 features as a flat list via to_feature_vector()
        windows_features = [r.to_feature_vector() for r in records]
        labels           = [r.danger_label for r in records]

        X = np.array(windows_features)  # shape (n_windows, 39)
        y = np.array(labels)

        if len(np.unique(y)) < 2:
            return False, "Not enough variety in data (need both SAFE and DANGER samples to train)."

        model = lgb.LGBMClassifier(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            random_state=42,
            verbosity=-1,
        )
        model.fit(X, y)

        accuracy = float(model.score(X, y))

        with io.BytesIO() as f:
            joblib.dump(model, f)
            model_bytes = f.getvalue()

        import time
        version = f"v3.{int(time.time())}"  # v3.x signals 39-feature model

        MLModel.query.filter_by(is_active=True).update({'is_active': False})
        new_model = MLModel(
            version=version,
            is_active=True,
            data=model_bytes,
            accuracy=accuracy,
        )
        db.session.add(new_model)
        db.session.commit()

        logging.info(f"Retraining successful: {version}, windows={len(X)}, accuracy={accuracy:.4f}")
        return True, f"Model {version} trained on {len(X)} windows. Accuracy: {accuracy:.4%}"

    except Exception as e:
        db.session.rollback()
        logging.error(f"Retrain failed: {e}")
        return False, str(e)
