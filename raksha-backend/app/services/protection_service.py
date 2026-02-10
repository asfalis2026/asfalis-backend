
import math
from app.services.sos_service import trigger_sos

# In-memory store for active protection status (mock)
# In production, use Redis or DB
active_protection_users = {}

def toggle_protection(user_id, is_active):
    if is_active:
        active_protection_users[user_id] = True
        return True, "Protection activated"
    else:
        active_protection_users.pop(user_id, None)
        return True, "Protection deactivated"

def get_protection_status(user_id):
    is_active = active_protection_users.get(user_id, False)
    return {
        "is_active": is_active,
        "bracelet_connected": False # Mock
    }

def analyze_sensor_data(user_id, sensor_type, readings, sensitivity):
    if not active_protection_users.get(user_id):
        return {"alert_triggered": False, "confidence": 0.0}

    # Mock Analysis Logic
    # Simple threshold detection for "fall" or "shake"
    threshold = 15.0 # m/s^2 approx (1.5G)
    if sensitivity == 'high': threshold = 12.0
    elif sensitivity == 'low': threshold = 20.0

    max_magnitude = 0.0
    for r in readings:
        mag = math.sqrt(r['x']**2 + r['y']**2 + r['z']**2)
        if mag > max_magnitude:
            max_magnitude = mag

    if max_magnitude > threshold:
        # Trigger SOS!
        # Assuming we can get user's last location
        from app.services.location_service import get_last_location
        last_loc = get_last_location(user_id)
        lat = last_loc.latitude if last_loc else 0.0
        lng = last_loc.longitude if last_loc else 0.0

        alert, msg = trigger_sos(user_id, lat, lng, trigger_type=f"auto_{sensor_type}")
        
        return {
            "alert_triggered": True,
            "alert_id": alert.id if alert else None,
            "confidence": 0.95
        }

    return {"alert_triggered": False, "confidence": 0.1}
