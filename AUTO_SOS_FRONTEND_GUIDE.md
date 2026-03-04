# Auto SOS — Frontend API Integration Guide

> **Base URL:** `https://<your-host>/api`  
> All protected endpoints require the header:  
> `Authorization: Bearer <access_token>`

---

## Table of Contents

1. [Overview & Architecture](#1-overview--architecture)
2. [Flow Diagram](#2-flow-diagram)
3. [Step-by-Step Integration](#3-step-by-step-integration)
   - [3.1 Toggle Auto SOS On/Off](#31-toggle-auto-sos-onoff)
   - [3.2 Read Protection Status on App Launch](#32-read-protection-status-on-app-launch)
   - [3.3 Device-Side Threshold Check (Frontend Only)](#33-device-side-threshold-check-frontend-only)
   - [3.4 Submit Sensor Window to ML Model](#34-submit-sensor-window-to-ml-model)
   - [3.5 Handle the SOS Countdown](#35-handle-the-sos-countdown)
   - [3.6 Submit Feedback (False Alarm / Confirmed Danger)](#36-submit-feedback-false-alarm--confirmed-danger)
4. [ML Model Internals (Reference)](#4-ml-model-internals-reference)
   - [4.1 Feature Vector (17 features)](#41-feature-vector-17-features)
   - [4.2 Sensor Type → SOS Trigger Type Mapping](#42-sensor-type--sos-trigger-type-mapping)
   - [4.3 Single Source of Truth](#43-single-source-of-truth)
5. [Alternative: Legacy Bulk Sensor Upload](#5-alternative-legacy-bulk-sensor-upload)
6. [Settings Sync](#6-settings-sync)
7. [Error Reference](#7-error-reference)
8. [Sensitivity Thresholds Cheatsheet](#8-sensitivity-thresholds-cheatsheet)
9. [Cooldown Rules](#9-cooldown-rules)

---

## 1. Overview & Architecture

The Auto SOS pipeline is a **two-stage system** that splits responsibility between the device and the backend:

| Stage | Where | What happens |
|---|---|---|
| **Stage 1 — Threshold guard** | Device (Frontend) | Accelerometer / gyroscope readings are checked locally. Only readings that exceed the user-configured magnitude threshold are forwarded to the backend. This saves battery and bandwidth. |
| **Stage 2 — Feature extraction** | Backend | Raw `[x, y, z]` readings in the submitted window are converted into a **17-feature vector** (15 statistical + 2 one-hot sensor-type encoding). The frontend never computes or sends features — this always happens server-side. |
| **Stage 3 — ML prediction** | Backend | The trained RandomForest model scores the feature vector. If the danger confidence meets the sensitivity threshold, an SOS countdown is created automatically. |

> **Important:** The frontend only ever sends raw sensor readings (`[x, y, z]`). Feature engineering is entirely a backend responsibility, keeping the model pipeline consistent regardless of which client is calling the API.

**The toggle lives in settings** (`auto_sos_enabled`). When it is `false` the backend refuses `/predict` requests entirely, so the frontend can skip sending data.

---

## 2. Flow Diagram

```
User toggles Auto SOS ON
        │
        ▼
Frontend starts listening to Accelerometer & Gyroscope
        │
        ▼ (every reading)
Compute magnitude = √(x² + y² + z²)
        │
        ├── magnitude ≤ threshold → discard, keep listening
        │
        └── magnitude > threshold
                │
                ▼
         Collect N raw [x, y, z] readings into a window (≥ 3, recommended 40)
                │
                ▼
         POST /api/protection/predict  (raw readings, no feature computation needed)
                │
                ▼  [Backend only — frontend does nothing here]
         extract_features(window, sensor_type)
           → 15 statistical features (mean, std, max, min, sum² per axis)
           → 2 one-hot features    (is_accelerometer, is_gyroscope)
           → 17-feature vector fed into RandomForest model
                │
                ├── prediction = 0 (safe) → keep listening
                │
                └── prediction = 1 (danger)
                        │
                        ▼
                 SOS countdown created  ←── response.data.alert_id
                        │
                 Show countdown UI (e.g. 30 s)
                        │
                 ┌──────┴──────────────┐
                 │                     │
           User cancels          Timer expires / User taps Send
                 │                     │
          POST /api/sos/cancel   POST /api/sos/send-now
                 │                     │
                 └──────┬──────────────┘
                        │
                 POST /api/protection/feedback/<alert_id>
                   { "is_false_alarm": true | false }
                        │
                 Training data re-labelled for next model run
```

---

## 3. Step-by-Step Integration

### 3.1 Toggle Auto SOS On/Off

Use either of the two equivalent approaches. **Approach A** (settings) is preferred because it also saves all other user preferences in the same call.

#### Approach A — via Settings (recommended)

```
PUT /api/settings
```

**Request**
```json
{
  "auto_sos_enabled": true
}
```

**Response `200`**
```json
{
  "success": true,
  "data": {
    "emergency_number": "911",
    "sos_message": "Emergency! ...",
    "shake_sensitivity": "medium",
    "battery_optimization": true,
    "haptic_feedback": true,
    "auto_sos_enabled": true
  }
}
```

> Turning this off (`false`) also clears the backend's in-memory cache so no stale data is processed.

---

#### Approach B — via Protection Toggle

```
POST /api/protection/toggle
```

**Request**
```json
{
  "is_active": true
}
```

**Response `200`**
```json
{
  "success": true,
  "message": "Auto SOS protection activated",
  "data": {
    "is_active": true,
    "bracelet_connected": false
  }
}
```

---

### 3.2 Read Protection Status on App Launch

Call this once on startup to restore the toggle UI state correctly (the backend is DB-backed so it survives restarts).

```
GET /api/protection/status
```

**Response `200`**
```json
{
  "success": true,
  "data": {
    "is_active": true,
    "bracelet_connected": false
  }
}
```

> Also available inside `GET /api/settings` as `auto_sos_enabled`.

---

### 3.3 Device-Side Threshold Check (Frontend Only)

> **No API call needed for this step.** All logic runs on-device.

**Algorithm**

```
magnitude = sqrt(x² + y² + z²)
```

Suggested threshold values (tune based on user's `shake_sensitivity` setting):

| `shake_sensitivity` | Recommended magnitude threshold |
|---|---|
| `low` | 25.0 m/s² |
| `medium` | 18.0 m/s² |
| `high` | 12.0 m/s² |

**Buffer strategy**
- Maintain a **rolling buffer** of the last N readings (recommended N = 40).
- When a reading exceeds the threshold, **snapshot the buffer** — that is your window to send.
- Send once per window; restart the buffer after sending to avoid flooding.

**Minimum window size:** 3 readings (backend enforces this). Accuracy improves significantly with ≥ 40 readings.

---

### 3.4 Submit Sensor Window to ML Model

Call this only when Stage 1 fires (magnitude exceeded threshold). **Do not call this continuously.**

```
POST /api/protection/predict
```

**Headers**
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request**
```json
{
  "window": [
    [0.12, -9.81, 0.34],
    [1.45, -9.60, 0.78],
    [3.22, -8.10, 2.10]
  ],
  "sensor_type": "accelerometer",
  "location": "Market Street, San Francisco"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `window` | `[[float, float, float], ...]` | ✅ | Array of raw `[x, y, z]` sensor readings. Min length: 3. Recommended: 40. **Do not pre-process — send raw values only.** |
| `sensor_type` | `string` | ❌ | `"accelerometer"` (default) or `"gyroscope"`. Used server-side for one-hot feature encoding. |
| `location` | `string` | ❌ | Human-readable label sent in WhatsApp alert |

> **What the backend does with your window (frontend does none of this):**
> 1. Computes 5 statistics (mean, std, max, min, sum of squares) for each of x, y, z → **15 features**
> 2. Appends a 2-element one-hot vector for `sensor_type`: `[1, 0]` for accelerometer, `[0, 1]` for gyroscope → **+2 features**
> 3. Feeds the resulting **17-feature vector** into the RandomForest model
> 4. Uses `predict_proba` confidence to decide whether to trigger SOS
>
> This extraction is the **single source of truth** shared by both the live prediction path and the model training pipeline, so training and inference are always consistent.

**Response — Safe `200`**
```json
{
  "success": true,
  "data": {
    "prediction": 0,
    "confidence": 0.21,
    "sensor_type": "accelerometer",
    "sos_sent": false
  }
}
```

**Response — Danger detected `200`**
```json
{
  "success": true,
  "data": {
    "prediction": 1,
    "confidence": 0.87,
    "sensor_type": "accelerometer",
    "sos_sent": true,
    "alert_id": "a1b2c3d4-...",
    "message": "SOS countdown started"
  }
}
```

> When `sos_sent = true`, **store `alert_id`** immediately — you'll need it for the countdown and feedback steps.

**Response — Toggle is off `200`**
```json
{
  "success": true,
  "data": {
    "prediction": 0,
    "confidence": 0.0,
    "sos_sent": false,
    "message": "Auto SOS is not enabled. Toggle it on first."
  }
}
```

**Response — Cooldown active `200`**
```json
{
  "success": true,
  "data": {
    "prediction": 1,
    "confidence": 0.91,
    "sos_sent": false,
    "message": "SOS on cooldown, please wait before triggering again."
  }
}
```

> Cooldown is **20 seconds** after any SOS event (manual or automatic). Do not re-send during this window.

---

### 3.5 Handle the SOS Countdown

When `sos_sent = true` you receive an `alert_id`. Show a countdown UI (recommended: 30 seconds). The user has three options:

#### Option A — Let the timer expire → dispatch SOS

```
POST /api/sos/send-now
```

**Request**
```json
{
  "alert_id": "a1b2c3d4-..."
}
```

**Response `200`**
```json
{
  "success": true,
  "message": "SOS Dispatched via WhatsApp"
}
```

After this, proceed to [Step 3.6](#36-submit-feedback-false-alarm--confirmed-danger) with `is_false_alarm: false`.

---

#### Option B — User cancels (false alarm)

```
POST /api/sos/cancel
```

**Request**
```json
{
  "alert_id": "a1b2c3d4-..."
}
```

**Response `200`**
```json
{
  "success": true,
  "message": "SOS Cancelled"
}
```

After this, proceed to [Step 3.6](#36-submit-feedback-false-alarm--confirmed-danger) with `is_false_alarm: true`.

---

#### Option C — After SOS was sent, user marks themselves safe

```
POST /api/sos/safe
```

**Request**
```json
{
  "alert_id": "a1b2c3d4-..."
}
```

**Response `200`**
```json
{
  "success": true,
  "message": "Safe notification sent to 2 contact(s)",
  "data": {
    "alert_id": "a1b2c3d4-...",
    "status": "cancelled",
    "resolution_type": "false_alarm",
    "contacts_notified": 2
  }
}
```

After this, proceed to [Step 3.6](#36-submit-feedback-false-alarm--confirmed-danger) with `is_false_alarm: true`.

---

### 3.6 Submit Feedback (False Alarm / Confirmed Danger)

**Always call this after an Auto SOS resolves.** It re-labels the sensor data that was captured at the time of the alert, improving the ML model on its next training run.

```
POST /api/protection/feedback/<alert_id>
```

**Request — user says it was a false alarm**
```json
{
  "is_false_alarm": true
}
```

**Request — user confirms it was real danger**
```json
{
  "is_false_alarm": false
}
```

**Response `200`**
```json
{
  "success": true,
  "message": "Feedback saved — 40 training record(s) re-labelled as safe."
}
```

**Error — alert not found `404`**
```json
{
  "success": false,
  "error": {
    "code": "ALERT_NOT_FOUND",
    "message": "Alert not found or does not belong to you"
  }
}
```

> **When to call this:**
> - After `POST /api/sos/cancel` → `is_false_alarm: true`
> - After `POST /api/sos/safe` → `is_false_alarm: true`
> - After `POST /api/sos/send-now` (real emergency confirmed) → `is_false_alarm: false`

---

## 4. ML Model Internals (Reference)

This section is informational only. **The frontend never needs to implement any of this.**

### 4.1 Feature Vector (17 features)

For every window of N raw `[x, y, z]` readings, the backend computes:

| # | Feature | Axis | Formula |
|---|---|---|---|
| 1 | Mean | x | `mean(x)` |
| 2 | Std Dev | x | `std(x)` |
| 3 | Max | x | `max(x)` |
| 4 | Min | x | `min(x)` |
| 5 | Sum of squares | x | `Σ(xᵢ²)` |
| 6–10 | Same 5 stats | y | — |
| 11–15 | Same 5 stats | z | — |
| 16 | One-hot: accelerometer | — | `1` if accelerometer, else `0` |
| 17 | One-hot: gyroscope | — | `1` if gyroscope, else `0` |

### 4.2 Sensor Type → SOS Trigger Type Mapping

| `sensor_type` sent by frontend | `trigger_type` stored in SOS alert |
|---|---|
| `accelerometer` | `auto_fall` |
| `gyroscope` | `auto_shake` |

### 4.3 Single Source of Truth

Both training paths (offline `scripts/train_model.py` and the in-app `POST /api/protection/train-model`) call the same `extract_features()` function that the live prediction path uses. This guarantees that the feature vector a model was trained on is **byte-for-byte identical** to the feature vector it scores at inference time. Adding or changing a feature in one place automatically propagates to all paths.

---

## 5. Alternative: Legacy Bulk Sensor Upload

This endpoint accepts a rolling batch of readings and runs both threshold and ML prediction in the backend. Use this if you prefer to offload all logic to the server (higher bandwidth, simpler frontend).

```
POST /api/protection/sensor-data
```

**Request**
```json
{
  "sensor_type": "accelerometer",
  "sensitivity": "medium",
  "data": [
    { "x": 0.12, "y": -9.81, "z": 0.34, "timestamp": 1709600000000 },
    { "x": 1.45, "y": -9.60, "z": 0.78, "timestamp": 1709600000050 }
  ]
}
```

| Field | Type | Values | Default |
|---|---|---|---|
| `sensor_type` | string | `accelerometer`, `gyroscope` | — |
| `sensitivity` | string | `low`, `medium`, `high` | `medium` |
| `data` | array | `{x, y, z, timestamp}` objects | — |

**Response `200`**
```json
{
  "success": true,
  "data": {
    "alert_triggered": true,
    "alert_id": "a1b2c3d4-...",
    "confidence": 0.84
  }
}
```

> **Note:** This endpoint still requires the Auto SOS toggle to be on. It also auto-saves the sensor data as (unverified) training data.

---

## 6. Settings Sync

Fetch and update all settings, including `auto_sos_enabled`, through the settings endpoints.

#### Read current settings

```
GET /api/settings
```

**Response `200`**
```json
{
  "success": true,
  "data": {
    "emergency_number": "911",
    "sos_message": "Emergency! I need help...",
    "shake_sensitivity": "medium",
    "battery_optimization": true,
    "haptic_feedback": true,
    "auto_sos_enabled": false
  }
}
```

#### Update settings (partial update supported)

```
PUT /api/settings
```

**Request** — send only the fields you want to change:
```json
{
  "shake_sensitivity": "high",
  "auto_sos_enabled": true
}
```

---

## 7. Error Reference

| HTTP | `error.code` | Meaning | Fix |
|---|---|---|---|
| `400` | `VALIDATION_ERROR` | Missing or invalid field | Check request body against schema |
| `400` | `ALREADY_RESOLVED` | Alert already cancelled/resolved | Don't re-submit for this `alert_id` |
| `401` | `UNAUTHORIZED` | Missing or invalid JWT | Re-authenticate |
| `401` | `TOKEN_EXPIRED` | Access token expired | Use refresh token to get a new one |
| `404` | `ALERT_NOT_FOUND` | `alert_id` doesn't exist or belongs to another user | Verify `alert_id` |
| `500` | `DB_ERROR` | Backend DB write failed | Retry after a short delay |

---

## 8. Sensitivity Thresholds Cheatsheet

The backend uses these confidence thresholds when deciding whether to trigger SOS via `/sensor-data`. The `/predict` endpoint always uses the model's 0.5 cutoff and you control sensitivity on-device via the magnitude threshold.

| `shake_sensitivity` | Backend confidence threshold | Behaviour |
|---|---|---|
| `high` | ≥ 35% | Very sensitive — triggers on mild anomalies |
| `medium` | ≥ 60% | Balanced — recommended default |
| `low` | ≥ 85% | Conservative — only fires on high-confidence danger |

---

## 9. Cooldown Rules

- After **any** SOS is triggered (manual or automatic), a **20-second cooldown** is enforced per user.
- During cooldown, `/predict` and `/sensor-data` return `sos_sent: false` with a cooldown message.
- The cooldown resets automatically; no API call is required.
- **Do not retry** `/predict` in a loop — wait for the cooldown to expire before re-enabling sensor streaming.

---

## Quick Reference — Endpoint Summary

| Method | Endpoint | Auth | Purpose |
|---|---|---|---|
| `GET` | `/api/protection/status` | ✅ JWT | Get toggle + bracelet state |
| `POST` | `/api/protection/toggle` | ✅ JWT | Toggle Auto SOS on/off |
| `POST` | `/api/protection/predict` | ✅ JWT | **Main Auto SOS endpoint** — submit window, get ML prediction, SOS triggered if danger |
| `POST` | `/api/protection/sensor-data` | ✅ JWT | Legacy: bulk upload + server-side threshold |
| `POST` | `/api/protection/feedback/<alert_id>` | ✅ JWT | Submit true/false alarm feedback after SOS resolves |
| `POST` | `/api/sos/trigger` | ✅ JWT | Manual SOS |
| `POST` | `/api/sos/send-now` | ✅ JWT | Dispatch SOS immediately (during countdown) |
| `POST` | `/api/sos/cancel` | ✅ JWT | Cancel countdown |
| `POST` | `/api/sos/safe` | ✅ JWT | Mark user safe after sent SOS |
| `GET` | `/api/settings` | ✅ JWT | Read all settings incl. `auto_sos_enabled` |
| `PUT` | `/api/settings` | ✅ JWT | Update settings incl. `auto_sos_enabled` |
