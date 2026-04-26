import time
import logging
import math
from app.config import settings
from app.extensions import db
from app.services.sos_service import trigger_sos

active_protection_users = {}
_sos_cooldown = {}
SOS_COOLDOWN_SECONDS = 600
_manual_sos_cooldown = {}
MANUAL_SOS_COOLDOWN_SECONDS = 20

SENSOR_TRIGGER_MAP = {
    "accelerometer": "auto_fall",
    "gyroscope":     "auto_shake",
}

def _is_on_cooldown(user_id, cooldown_seconds=None):
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
    _sos_cooldown[user_id] = time.time()

def _is_manual_on_cooldown(user_id):
    last_trigger = _manual_sos_cooldown.get(user_id)
    if last_trigger is None:
        return False, 0
    elapsed = time.time() - last_trigger
    if elapsed < MANUAL_SOS_COOLDOWN_SECONDS:
        return True, int(MANUAL_SOS_COOLDOWN_SECONDS - elapsed)
    return False, 0

def _mark_manual_sos_triggered(user_id):
    _manual_sos_cooldown[user_id] = time.time()

def _clear_manual_cooldown(user_id):
    _manual_sos_cooldown.pop(user_id, None)

def toggle_protection(user_id, is_active):
    from app.models.settings import UserSettings
    settings_obj = UserSettings.query.filter_by(user_id=user_id).first()
    if not settings_obj:
        settings_obj = UserSettings(user_id=user_id)
        db.session.add(settings_obj)

    settings_obj.auto_sos_enabled = is_active
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return False, f"Failed to update protection state: {e}"

    if is_active:
        active_protection_users[user_id] = True
        return True, "Auto SOS protection activated"
    else:
        active_protection_users.pop(user_id, None)
        return True, "Auto SOS protection deactivated"

def _is_protection_active(user_id):
    if active_protection_users.get(user_id):
        return True
    try:
        from app.models.settings import UserSettings
        settings_obj = UserSettings.query.filter_by(user_id=user_id).first()
        if settings_obj and settings_obj.auto_sos_enabled:
            active_protection_users[user_id] = True
            return True
    except Exception:
        pass
    return False

def get_protection_status(user_id):
    is_active = _is_protection_active(user_id)
    from app.models.device import ConnectedDevice
    device = ConnectedDevice.query.filter_by(user_id=user_id, is_connected=True).first()
    bracelet_connected = (device is not None)
    return {
        "is_active": is_active,
        "bracelet_connected": bracelet_connected
    }

def analyze_sensor_data(user_id, sensor_type, readings, sensitivity):
    if not _is_protection_active(user_id):
        return {"alert_triggered": False, "confidence": 0.0}

    window_data = [[r['x'], r['y'], r['z']] for r in readings]

    # Simple magnitude threshold without ML
    max_mag = 0
    for r in window_data:
        mag = math.sqrt(r[0]**2 + r[1]**2 + r[2]**2)
        if mag > max_mag:
            max_mag = mag

    confidence_danger = min(max_mag / 30.0, 1.0)
    
    thresholds = {"high": 0.35, "medium": 0.60, "low": 0.85}
    s_key = (sensitivity or "medium").lower()
    threshold = thresholds.get(s_key, 0.60)
    is_danger = confidence_danger >= threshold

    if is_danger:
        from app.models.settings import UserSettings
        fresh_settings = UserSettings.query.filter_by(user_id=user_id).first()
        if not (fresh_settings and fresh_settings.auto_sos_enabled):
            return {"alert_triggered": False, "confidence": confidence_danger, "message": "Auto SOS suppressed: system is disarmed."}

        on_cooldown, secs_left = _is_on_cooldown(user_id)
        if on_cooldown:
            mins_left = (secs_left + 59) // 60
            return {
                "alert_triggered": False, "confidence": confidence_danger,
                "message": f"Auto SOS rate-limited. Next trigger allowed in {mins_left} min.",
                "retry_after_seconds": secs_left,
            }

        from app.services.location_service import get_last_location
        last_loc = get_last_location(user_id)
        lat = last_loc.latitude if last_loc else 0.0
        lng = last_loc.longitude if last_loc else 0.0

        trigger_type = SENSOR_TRIGGER_MAP.get(sensor_type, "auto_fall")
        trigger_reason = "Unusual fall detected" if sensor_type == "accelerometer" else "Unusual shake/motion detected"
        trigger_prefix = f"⚠️ AUTO-SOS: {trigger_reason} ({int(confidence_danger * 100)}% confidence)\nSensor: {sensor_type} | System was armed at time of trigger"
        
        alert, msg, countdown_seconds = trigger_sos(
            user_id, lat, lng, trigger_type=trigger_type,
            trigger_prefix=trigger_prefix, trigger_reason=trigger_reason,
        )
        _mark_sos_triggered(user_id)

        if alert:
            try:
                from app.services.fcm_service import send_push_notification
                from app.models.user import User
                user = db.session.get(User, user_id)
                if user and user.fcm_token:
                    send_push_notification(
                        fcm_token=user.fcm_token, title="⚠️ Auto SOS Triggered",
                        body=f"{trigger_reason} — tap to cancel within {countdown_seconds}s",
                        data={"type": "AUTO_SOS_COUNTDOWN", "alert_id": str(alert.id), "countdown_seconds": str(countdown_seconds)},
                    )
            except Exception:
                pass

        return {
            "alert_triggered": True, "alert_id": alert.id if alert else None,
            "confidence": confidence_danger, "trigger_reason": trigger_reason, "countdown_seconds": countdown_seconds,
        }

    return {"alert_triggered": False, "confidence": confidence_danger}

def predict_from_window(user_id, window_data, sensor_type='accelerometer', location="Unknown", latitude=None, longitude=None):
    if not _is_protection_active(user_id):
        return {"prediction": 0, "confidence": 0.0, "sos_sent": False, "message": "Auto SOS is not enabled. Toggle it on first."}

    # Trust device's local threshold completely without ML
    prediction, confidence = 1, 1.0

    response = {"prediction": prediction, "confidence": confidence, "sensor_type": sensor_type}

    if prediction == 1:
        from app.models.settings import UserSettings
        fresh_settings = UserSettings.query.filter_by(user_id=user_id).first()
        if not (fresh_settings and fresh_settings.auto_sos_enabled):
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
        trigger_reason = "Unusual fall detected" if sensor_type == "accelerometer" else "Unusual shake/motion detected"
        trigger_prefix = f"⚠️ AUTO-SOS: {trigger_reason} ({int(confidence * 100)}% confidence)\nSensor: {sensor_type} | Location: {location} | System was armed"
        
        alert, msg, countdown_seconds = trigger_sos(
            user_id, lat, lng, trigger_type=trigger_type,
            trigger_prefix=trigger_prefix, trigger_reason=trigger_reason,
        )
        _mark_sos_triggered(user_id)

        if alert:
            try:
                from app.services.fcm_service import send_push_notification
                from app.models.user import User
                user = db.session.get(User, user_id)
                if user and user.fcm_token:
                    send_push_notification(
                        fcm_token=user.fcm_token, title="⚠️ Auto SOS Triggered",
                        body=f"{trigger_reason} — tap to cancel within {countdown_seconds}s",
                        data={"type": "AUTO_SOS_COUNTDOWN", "alert_id": str(alert.id), "countdown_seconds": str(countdown_seconds)},
                    )
            except Exception:
                pass

        response["sos_sent"] = True
        response["alert_id"] = alert.id if alert else None
        response["message"] = msg
        response["trigger_reason"] = trigger_reason
        response["countdown_seconds"] = countdown_seconds

    else:
        response["sos_sent"] = False

    return response


def submit_sos_feedback(user_id, alert_id, is_false_alarm=True):
    """
    Stub for submitting feedback on an SOS trigger.
    Previously handled ML dataset updates; now just logs.
    """
    logger.info(f"Feedback received for alert {alert_id} (user={user_id}): false_alarm={is_false_alarm}")
    return True
