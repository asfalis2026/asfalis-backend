# Advanced Infrastructure & Real-Time Communication

This document provides a deep-dive into the "Engine" components of Asfalis that handle low-latency data delivery, high-priority push notifications, and hardware-software synchronization.

---

## 📡 1. Real-Time Location Streaming (WebSockets)

Asfalis utilizes **Flask-SocketIO** to provide a persistent, bi-directional communication channel between the user and their trusted contacts during an active emergency.

### Room-Based Privacy Model
To ensure that location data is only seen by authorized individuals, we use a **Room-based architecture**:
- **Namespace**: Default `/`
- **Room ID Strategy**: Every user has a unique room named `tracking_{user_id}`.
- **Access Control**: When a trusted contact opens the "Follow User" map in their app, they join the room associated with the person in danger.
- **Emission Logic**: Coordinates are emitted only to that specific room. This prevents data leakage and reduces the overhead on the server by not broadcasting to all connected clients.

### Concurrency & Compatibility
We use `async_mode='threading'` in the `SocketIO` configuration. This choice was made to ensure compatibility with **Python 3.13+**, avoiding the dependency issues often found with heavier asynchronous libraries like Eventlet or Gevent while maintaining enough performance for real-time safety tracking.

```python
# app/services/location_service.py
socketio.emit('location_update', {
    'user_id': user_id,
    'latitude': lat,
    'longitude': lng,
    'timestamp': datetime.utcnow().isoformat()
}, room=f"tracking_{user_id}")
```

---

## 🔔 2. Push Notification Pipeline (FCM)

The **Firebase Cloud Messaging (FCM)** service is the primary channel for non-SMS alerts (e.g., when a contact is added or an SOS is triggered).

### Emergency Bypass Configuration
For SOS alerts, we configure the FCM payload with Android-specific high-priority flags:
- **Priority**: `high` (Required to wake up a phone in Doze mode).
- **Channel ID**: `sos_channel`. This channel is pre-configured in the Android app with `importance=MAX` and a custom **Alarm Sound**.
- **Visuals**: Notifications include specific `data` payloads (e.g., `alert_id`) that allow the receiving app to immediately open the emergency map without user interaction.

```python
# app/services/fcm_service.py
android=messaging.AndroidConfig(
    priority='high',
    notification=messaging.AndroidNotification(
        channel_id='sos_channel', # Vibrates & plays loud sound
        priority='max',
        sound='alarm'
    )
)
```

---

## 💬 3. WhatsApp Dispatch Engine (Twilio)

The WhatsApp service is characterized by its **Structured Body Assembly** and **Synchronous Error Reporting**.

### The "Dispatch Report" Concept
Unlike standard "fire-and-forget" SMS, every SOS dispatch in Asfalis returns a **Delivery Report**. This is critical because in the Twilio Sandbox environment, a message might fail if the recipient hasn't joined.
- **Synchronous Logic**: The backend waits for Twilio's API response for *each* contact.
- **Error Mapping**: We map internal Twilio codes (e.g., `63016`, `63001`) to human-readable statuses like `not_in_sandbox` or `account_suspended`.
- **Result**: The user's app receives a list of which contacts were successfully reached and which need an alternative notification method.

### Message Templating
The message body is assembled dynamically based on the **Trigger Type**:
- Manual tap: "🔴 Manual SOS"
- Fall detected: "⚠️ Auto-SOS (Accelerometer)"
- IoT Button: "📣 Wearable Button SOS"

---

## 🧵 4. Lifecycle of Background Tasks

To maintain a responsive API, we separate the "Critical Path" (saving an alert to the DB) from the "Notification Path" (sending SMS/WhatsApp).

### Threaded Dispatch
The system uses Python's native `threading` module to handle:
1.  **Welcome SMS**: When a contact is verified, the 200 OK is returned to the user instantly while the SMS is sent in the background.
2.  **ML Model Retraining**: Training on thousands of sensor points can take 5-10 seconds. This is run in a background thread to prevent the client from hitting a gateway timeout.

---

## 🔋 5. Wearable Health & IoT Binding

The backend acts as a **State Machine** for the Asfalis Wearable:
- **IMEI/MAC Hard-Binding**: Each device is bound to a `user_id` in the `connected_devices` table.
- **Heartbeat & Battery**: The device sends periodic checks. If the battery falls below **15%**, the backend flags it in the user settings profile so the Android app can show a persistent "Low Battery" warning, ensuring the device doesn't fail when needed most.
- **Double-Tap Intel**: The backend detects "Double Taps" on the wearable button (two events within 1.5 seconds) and processes this as a **Force Cancel** for any active SOS alerts.
