# SOS Triggering: Multi-Path Emergency Infrastructure

Asfalis is designed to ensure that an emergency alert can be triggered in any situation—whether the user can reach their phone or not. This document explains the different trigger techniques, their code implementation, and the biological/mechanical theory behind them.

---

## 🚦 The "Grace Period" Architecture

Every SOS trigger in Asfalis follows a two-state lifecycle to prevent accidental dispatch:

1.  **`countdown` State**: The alert is created, but no contacts are notified yet. The user sees a 10-20 second cancellation window on their phone.
2.  **`sent` State**: If the timer expires or the user taps "Send Now", the system transitions to `sent`, and WhatsApp/FCM notifications are dispatched to all emergency contacts.

---

## 1. 🔴 Manual Trigger
The most direct path, used when the user has their phone out and can tap the physical or on-screen SOS button.

-   **Theory**: Focused on speed. Bypasses sensor logic entirely.
-   **Security**: Requires a specialized **`sos_token`** (valid for 30 days) to ensure the button works even if the user's login session has expired.
-   **Cooldown**: **20 seconds**. Prevents accidental double-triggers from multiple button taps.

### Code snippet: Manual Dispatch
```python
# app/routes/sos.py
@sos_bp.route('/trigger', methods=['POST'])
@jwt_required()
def trigger():
    current_user_id = get_jwt_identity()
    # verify user has contacts before starting
    # ...
    alert, msg = trigger_sos(current_user_id, lat, lng, trigger_type='manual')
    return jsonify(success=True, data=payload), 201
```

---

## 2. 🧠 Auto-SOS (Fall & Motion Detection)
Real-time analysis of accelerometer and gyroscope data.

-   **Theory**: Uses **Euclidean Distance** between successive points. If the magnitude of motion exceeds a threshold, the system analyzes a **40-point window** (approx. 2 seconds) using a **Random Forest ML model**.
-   **Trigger Types**: 
    -   `auto_fall`: High impact followed by zero motion (accelerometer).
    -   `auto_shake`: Vigorous, repetitive motion (gyroscope).
-   **Cooldown**: **10 minutes**. This is critical to prevent a single accident from spamming contacts with dozens of alerts per second.

### Code snippet: ML Prediction & Cooldown
```python
# app/services/protection_service.py
def analyze_sensor_data(user_id, sensor_type, readings, sensitivity):
    # 1. Prediction
    prediction, confidence = predict_danger(window_data, sensor_type)
    
    # 2. Threshold Check (Sensitivity mapped to prob_danger)
    if confidence >= thresholds.get(sensitivity):
        # 3. Cooldown Check
        on_cooldown, _ = _is_on_cooldown(user_id)
        if not on_cooldown:
            trigger_sos(user_id, lat, lng, trigger_type='auto_fall')
            _mark_sos_triggered(user_id) # Start 10 min clock
```

---

## ⌚ 3. IoT Wearable (Bluetooth Bracelet)
Integration with hardware devices (e.g., ESP32 based bracelets).

-   **Theory**: Uses Bluetooth Low Energy (BLE). The bracelet sends a specific byte sequence to the user's phone.
-   **Advanced Usage**: **Single Press vs. Double-Tap**.
    -   User presses once: SOS Triggered.
    -   User taps twice within **1.5 seconds**: **Active SOS Cancelled**.
-   **Advantage**: Works even if the phone is in a pocket, bag, or across the room.

### Code snippet: Double-Tap Cancellation Logic
```python
# app/routes/device.py
@device_bp.route('/button-event', methods=['POST'])
def iot_button_event():
    now = datetime.utcnow()
    # Check if this press happened quickly after the last one
    if device.last_button_press_at and (now - device.last_button_press_at).total_seconds() <= 1.5:
        # It's a double-tap! CANCEL the SOS instead of triggering
        cancel_sos(active_alert.id, current_user_id)
        return jsonify(action='cancelled'), 200
    
    # Otherwise, it's a single press - TRIGGER SOS
    trigger_sos(user_id, lat, lng, trigger_type='iot_button')
```

---

## 📡 4. Multichannel Dispatch
Once an alert moves from `countdown` to `sent`, the system dispatches coordinates through the **WhatsApp Dispatch Engine**.

-   **WhatsApp Sandbox**: During development, recipients must join the Twilio sandbox. The system handles specific errors (e.g., `not_in_sandbox`) to provide feedback to the sender.
-   **Structured Body**: Messages include:
    -   **User Name**
    -   **Trigger Type** (so contacts know if it was a manual tap or a detected fall)
    -   **Google Maps Link** (latitude/longitude)
    -   **Reason** (e.g., "98% confidence fall detection")

### Code snippet: WhatsApp Assembly
```python
# app/services/whatsapp_service.py
def _build_sos_body(user_name, trigger_type, trigger_reason, maps_link):
    label = TRIGGER_TYPE_LABELS.get(trigger_type)
    return f"🚨 EMERGENCY: {user_name} needs help!\nTrigger: {label}\n📍 Location: {maps_link}"
```

---

## 🛠️ Summary of Cooldowns

| Trigger Type | Cooldown Duration | Purpose |
| :--- | :--- | :--- |
| **Manual** | 20 Seconds | Prevents accidental double-calls. |
| **Auto-SOS** | 10 Minutes | Prevents alert storm from a single event. |
| **IoT Button** | None (Backend) | Handled by Android `IotSosTracker` to remain responsive for cancellation. |
