# IoT Wearable — Backend Contract

> Last updated: 5 March 2026
> Audience: Backend team
> Companion doc: `IOT_WEARABLE_ANDROID_GUIDE.md` (hardware/Android layer)

---

## Overview

The ESP32 Classic Bluetooth wearable exposes a single physical button. The **Android app owns all press logic** — double-tap detection, countdown state, cooldown enforcement, and API calls. The backend does **not** receive raw button events and does **not** need any new dedicated endpoints.

The app reuses the existing SOS API with one new `trigger_type` value (`"iot_button"`). Every other behavior (cancel, safe, send-now) is identical to the manual-SOS flow.

---

## 1 — Press Logic Summary (app-side, for reference)

The backend team does not implement any of the rows below. This table describes **why** the existing SOS endpoints are called, and in which order, so error handling expectations are clear.

| Press pattern | App-side condition | API call made |
|---|---|---|
| Single tap (gap ≥ 1 500 ms from last press) | No 10-min hardware cooldown active | `POST /api/sos/trigger` |
| Single tap | Hardware cooldown active (post-dispatch, < 10 min) | No API call |
| Double tap (gap < 1 500 ms) | SOS is in countdown phase | `POST /api/sos/cancel` |
| Double tap | SOS was dispatched < 60 s ago | `POST /api/sos/safe` |
| Double tap | No active SOS | No API call |

All cooldown timers and state tracking live entirely in `IotSosTracker` (in-memory singleton) and `SosViewModel` on the Android side.

---

## 2 — API Endpoints the App Calls

All requests are authenticated with the existing `Authorization: Bearer <access_token>` header. Base URL: `https://asfalis-backend.onrender.com/api/`

### 2.1 — Trigger SOS via wearable button

```
POST /api/sos/trigger
```

**Request body**

```json
{
  "trigger_type": "iot_button",
  "latitude": 22.5726,
  "longitude": 88.3639,
  "accuracy": null
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `trigger_type` | string | ✅ | Must be `"iot_button"` for hardware-originated alerts. Backend should persist this for history/analytics. |
| `latitude` | number | ✅ | GPS coordinate from the phone (not the ESP32). `0.0` if location unavailable. |
| `longitude` | number | ✅ | GPS coordinate from the phone. `0.0` if location unavailable. |
| `accuracy` | number | ❌ | Always `null` from the wearable path (no accuracy metadata). |

**Success response `200`**

```json
{
  "status": "success",
  "data": {
    "alert_id": "abc123",
    "status": "countdown",
    "countdown_seconds": 10,
    "contacts_to_notify": 3
  }
}
```

The app reads `alert_id` from the response and stores it in `IotSosTracker` for all subsequent cancel/safe calls.

**⚠ Backend requirement:** The `trigger_type` field must be accepted and stored. If the backend currently validates `trigger_type` against an allowlist, add `"iot_button"` to it alongside `"manual"`, `"auto"`, etc.

---

### 2.2 — Cancel SOS (countdown phase, double-tap)

```
POST /api/sos/cancel
```

**Request body**

```json
{
  "alert_id": "abc123"
}
```

**Success response `200`**

```json
{
  "status": "success",
  "data": null
}
```

Called only when the countdown is still active (not yet dispatched). Behavior is identical to the user pressing "I'm Safe" on the SOS screen during countdown.

---

### 2.3 — Mark User Safe (dispatched phase, double-tap)

```
POST /api/sos/safe
```

**Request body**

```json
{
  "alert_id": "abc123"
}
```

**Success response `200`**

```json
{
  "status": "success",
  "data": null
}
```

Called when the SOS was already dispatched to contacts but the user presses the wearable button again within 60 seconds. This notifies contacts that the user is safe — identical behavior to the UI "I'm Safe" button post-dispatch.

---

### 2.4 — Send Now (not directly from wearable, but related)

```
POST /api/sos/send-now
```

Not triggered by a wearable button press. Included here for completeness — the wearable flow does not call this endpoint. The app calls it from the SOS countdown screen (manual "Send Now" tap or countdown expiry).

---

## 3 — trigger_type Values — Full Allowlist

The backend should accept all of the following values for `trigger_type` in `POST /api/sos/trigger`:

| Value | Source |
|---|---|
| `"manual"` | User taps the manual SOS button in-app |
| `"auto"` | Auto-SOS triggered by accelerometer / inactivity |
| `"iot_button"` | **New** — hardware wearable button single-tap |

---

## 4 — Error Codes the App Handles

The app's `IotWearableManager` processes these error cases silently (no crash, log-only):

| HTTP Status | `error_code` | App behavior |
|---|---|---|
| `400` | `ALREADY_RESOLVED` | Log warning; SOS was already cancelled — do nothing |
| `401` | `UNAUTHORIZED` | Log error; token likely expired — user must re-login via UI |
| `404` | `ALERT_NOT_FOUND` | Log warning; stale `alert_id` in tracker — auto-resolve tracker state |
| `5xx` | Any | Log error; no retry from service — user sees no feedback |

---

## 5 — What the Backend Does NOT Need to Change

| Concern | Where it lives |
|---|---|
| Double-tap detection (1 500 ms window) | `IotWearableManager` (Android) |
| 10-minute hardware cooldown | `IotSosTracker` (Android in-memory) |
| 60-second "recently dispatched" cancel window | `IotSosTracker` (Android in-memory) |
| BT connection management | `IotWearableService` foreground service (Android) |
| Button event forwarding / debounce table | Not needed — app handles everything |
| `/api/device/button-event` endpoint | Not called by the new architecture |

The backend is a pure SOS state machine from its own perspective. It does not know whether an SOS came from the UI or the wearable — it only sees `trigger_type: "iot_button"` instead of `"manual"`.

---

## 6 — SOS History Display (optional enhancement)

The `GET /api/sos/history` response already returns `trigger_type` per alert (see `SosHistoryItem` DTO). If the backend stores `"iot_button"` correctly from step 2.1, the app's SOS history screen will automatically display wearable-originated alerts distinctly (label mapping can be added to the UI independently).

---

## 7 — Backend Checklist

- [ ] **`POST /api/device/register` is reachable and returns `200`** *(critical — app won't connect without this)*
  - Request: `{ "device_name": "ESP32_SOS_DEVICE", "device_mac": "<mac>", "firmware_version": "1.0.0" }`
  - Response must include `data.device_id` (string)
  - If this endpoint returns any error, the device ID is not saved — `PUT /api/device/<id>/status` on disconnect will also fail
- [ ] **`"iot_button"` is accepted by `POST /api/sos/trigger`** *(critical — trigger is rejected silently if not allowlisted)*
- [ ] Confirm `trigger_type` is persisted in the SOS alert record
- [ ] Confirm `POST /api/sos/cancel` enforces alert ownership (already hardened per safety layer doc)
- [ ] Confirm `POST /api/sos/safe` works for alerts in both `countdown` and `sent` states
- [ ] Confirm `GET /api/sos/history` returns `trigger_type` in each record
- [ ] *(Optional)* Add `"iot_button"` to any analytics/notification templates that display trigger source

> **Note on registration:** The app now starts the BT connection immediately without waiting for
> `POST /api/device/register` to succeed (registration failure is non-fatal). However the endpoint
> must still exist and return a valid `device_id` for the disconnect flow
> (`PUT /api/device/<id>/status`) to work correctly.

No new endpoints, no new tables, and no migration are required.
