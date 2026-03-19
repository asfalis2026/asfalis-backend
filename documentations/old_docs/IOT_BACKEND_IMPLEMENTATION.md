# Asfalis IoT Wearable — Backend Implementation Reference

> **Last updated:** 11 March 2026  
> **Status:** ✅ Fully implemented and contract-compliant  
> **Architecture:** App-side tap detection (Android `IotSosTracker`) → standard SOS endpoints

---

## Table of Contents

1. [System Architecture](#1-system-architecture)
2. [Hardware Summary (ESP32 Firmware)](#2-hardware-summary-esp32-firmware)
3. [Database Changes](#3-database-changes)
4. [Device Management Endpoints](#4-device-management-endpoints)
   - [POST /api/device/register](#41-post-apideviceregister)
   - [GET /api/device/status](#42-get-apidevicestatus)
   - [PUT /api/device/{id}/status](#43-put-apideviceidstatus)
   - [DELETE /api/device/{id}](#44-delete-apideviceid)
   - [POST /api/device/button-event (legacy)](#45-post-apidevicebutton-event-legacy)
5. [SOS Endpoints (IoT Path)](#5-sos-endpoints-iot-path)
   - [POST /api/sos/trigger](#51-post-apissostrigger)
   - [POST /api/sos/cancel](#52-post-apissoscancel)
   - [POST /api/sos/safe](#53-post-apisosnilsafe)
   - [POST /api/sos/send-now](#54-post-apissossend-now)
   - [GET /api/sos/history](#55-get-apissoshistory)
6. [SOS State Machine](#6-sos-state-machine)
7. [Service Layer Changes](#7-service-layer-changes)
8. [Schema / Validation Changes](#8-schema--validation-changes)
9. [Configuration Variables](#9-configuration-variables)
10. [Error Code Reference](#10-error-code-reference)
11. [End-to-End IoT SOS Flow](#11-end-to-end-iot-sos-flow)
12. [What Was Done — Change Log](#12-what-was-done--change-log)

---

## 1. System Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│  ESP32 Wearable                                                      │
│  - Physical button triggers BT frame: "SOS_TRIGGER_RANDOM_MESSAGE"  │
│  - Every press sends identical frame. Firmware has NO tap logic.     │
└────────────────────┬─────────────────────────────────────────────────┘
                     │  Bluetooth Classic SPP (Serial Port Profile)
                     ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Android App — IotSosTracker                                         │
│  - Receives BT frames                                                │
│  - Owns ALL tap logic (single tap = trigger, double-tap = cancel)    │
│  - Double-tap window: configurable, default 1.5 s                   │
│  - On single tap  → POST /api/sos/trigger  {trigger_type:"iot_button"} │
│  - On double-tap  → POST /api/sos/cancel   {alert_id}               │
└────────────────────┬─────────────────────────────────────────────────┘
                     │  HTTPS + Bearer JWT
                     ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Flask Backend (Asfalis)                                             │
│  - Treats iot_button as just another trigger_type                    │
│  - No tap-detection logic on server side                             │
│  - Persists SOSAlert, sends WhatsApp via Twilio, FCM push            │
└──────────────────────────────────────────────────────────────────────┘
```

**Key principle:** The backend is tap-logic-agnostic. It receives standard REST calls and treats `trigger_type: "iot_button"` identically to `"manual"`. All timing decisions live in the app.

---

## 2. Hardware Summary (ESP32 Firmware)

| Property | Value |
|---|---|
| Hardware | ESP32 microcontroller inside wrist wearable |
| BT protocol | **Classic SPP** (Serial Port Profile) — NOT BLE/GATT |
| Button message | `"SOS_TRIGGER_RANDOM_MESSAGE"` (fixed string, every press) |
| Tap counting | ❌ None — every press is identical |
| GPS | ❌ Not present — sends `accuracy: null` |
| Battery reporting | Not implemented in current firmware |

The firmware **cannot be changed**. The backend and app must adapt to its single-message output.

---

## 3. Database Changes

### 3.1 Migrations Applied

| Migration file | What it adds |
|---|---|
| `c1d2e3f4g5h6_add_iot_button_support.py` | `last_button_press_at` column on `connected_devices`; `iot_button` added to `trigger_type_enum` in PostgreSQL |

### 3.2 `connected_devices` Table — Current Schema

| Column | Type | Notes |
|---|---|---|
| `id` | `VARCHAR(36)` PK | UUID |
| `user_id` | `VARCHAR(36)` FK → `users.id` | Owner |
| `device_name` | `VARCHAR(100)` | Human-readable label |
| `device_mac` | `VARCHAR(17)` | `AA:BB:CC:DD:EE:FF` format |
| `is_connected` | `BOOLEAN` | Current connection state |
| `firmware_version` | `VARCHAR(20)` nullable | |
| `battery_level` | `INTEGER` nullable | Percentage, not yet reported by firmware |
| `last_seen` | `DATETIME` nullable | Updated on every PUT /status call |
| `paired_at` | `DATETIME` | When first registered |
| `last_button_press_at` | `DATETIME` nullable | ✅ Added — records last ESP32 button press (used by legacy `/button-event` only) |

### 3.3 `sos_alerts` Table — Relevant Columns

| Column | Type | Values |
|---|---|---|
| `trigger_type` | ENUM | `manual`, `auto_fall`, `auto_shake`, `bracelet`, **`iot_button`** ✅ |
| `status` | ENUM | `countdown`, `sent`, `cancelled`, `resolved` |
| `resolution_type` | `VARCHAR(50)` | `cancelled`, `false_alarm`, `user_marked_safe`, `timeout`, `manual_resolution` |

---

## 4. Device Management Endpoints

All device endpoints require `Authorization: Bearer <access_token>`.

### 4.1 POST /api/device/register

Pair the ESP32 wearable to the authenticated user's account. Idempotent — re-registering the same MAC transfers ownership to the current user and marks it connected.

**Request**
```json
{
  "device_name": "My Wristband",
  "device_mac": "AA:BB:CC:DD:EE:FF",
  "firmware_version": "1.0.2"
}
```

| Field | Required | Notes |
|---|---|---|
| `device_name` | ✅ | Display label |
| `device_mac` | ✅ | 17-char MAC (`XX:XX:XX:XX:XX:XX`) |
| `firmware_version` | No | `null` accepted |

Extra/unknown fields are silently ignored (`EXCLUDE` meta).

**Response — 201 Created**
```json
{
  "success": true,
  "data": {
    "device_id": "uuid-string",
    "device_name": "My Wristband",
    "device_mac": "AA:BB:CC:DD:EE:FF",
    "is_connected": true,
    "battery_level": null,
    "firmware_version": "1.0.2",
    "signal_strength": null,
    "last_seen": "2026-03-11T10:00:00.000000",
    "last_button_press_at": null
  }
}
```

**Error Responses**

| HTTP | code | When |
|---|---|---|
| `400` | `VALIDATION_ERROR` | Missing `device_name` or `device_mac` |

---

### 4.2 GET /api/device/status

Returns the most recently seen device for the authenticated user.

**Request** — no body

**Response — 200 OK (device found)**
```json
{
  "success": true,
  "data": {
    "device_id": "uuid-string",
    "device_name": "My Wristband",
    "device_mac": "AA:BB:CC:DD:EE:FF",
    "is_connected": true,
    "battery_level": null,
    "firmware_version": "1.0.2",
    "signal_strength": null,
    "last_seen": "2026-03-11T10:05:00.000000",
    "last_button_press_at": null
  }
}
```

**Response — 200 OK (no device paired)** ✅ Not 404
```json
{
  "success": true,
  "data": null
}
```

> **Why 200?** The app checks `response.isSuccessful && data != null` to determine pairing state. A 404 would be treated as a network error, not "no device".

---

### 4.3 PUT /api/device/{id}/status

Called by the app on BLE connect and BLE disconnect events. Updates `is_connected` and always stamps `last_seen`.

**URL parameter:** `id` — the `device_id` UUID from the register response.

**Request**
```json
{
  "is_connected": false
}
```

| Field | Required | Notes |
|---|---|---|
| `is_connected` | ✅ | `true` = connected, `false` = disconnected |

**Response — 200 OK**
```json
{
  "success": true,
  "data": {
    "device_id": "uuid-string",
    "device_name": "My Wristband",
    "device_mac": "AA:BB:CC:DD:EE:FF",
    "is_connected": false,
    "battery_level": null,
    "firmware_version": "1.0.2",
    "signal_strength": null,
    "last_seen": "2026-03-11T10:10:00.000000",
    "last_button_press_at": null
  }
}
```

> **`last_seen` is always updated** — on both connect and disconnect. Previously it was only updated on connect; this was a bug and has been fixed.

**Error Responses**

| HTTP | code | When |
|---|---|---|
| `404` | `NOT_FOUND` | `device_id` doesn't exist or belongs to another user |

---

### 4.4 DELETE /api/device/{id}

Unpair / remove a device from the user's account.

**URL parameter:** `id` — the `device_id` UUID.

**Response — 200 OK**
```json
{
  "success": true,
  "message": "Device removed"
}
```

**Error Responses**

| HTTP | code | When |
|---|---|---|
| `404` | `NOT_FOUND` | `device_id` doesn't exist or belongs to another user |

---

### 4.5 POST /api/device/button-event (legacy)

> ⚠️ **Legacy endpoint — do not use in new implementations.**
>
> This endpoint implemented server-side double-tap detection (the old architecture). It is retained in the codebase for backward compatibility but is superseded by the app-side `IotSosTracker` architecture. New app builds should call `/api/sos/trigger` and `/api/sos/cancel` directly.

The endpoint remains functional but reflects the old flow where the backend decided whether a button press was a single-tap (trigger) or double-tap (cancel). In the current architecture, the Android app makes that decision.

---

## 5. SOS Endpoints (IoT Path)

These are standard SOS endpoints. The IoT wearable path uses them exactly like any other SOS trigger — only `trigger_type` differs.

All SOS endpoints require `Authorization: Bearer <access_token>` or `Authorization: Bearer <sos_token>` (long-lived token issued at login, valid for 30 days).

### 5.1 POST /api/sos/trigger

Starts a countdown SOS. Called by `IotSosTracker` on single-tap detection.

**Request**
```json
{
  "latitude": 22.5726,
  "longitude": 88.3639,
  "trigger_type": "iot_button",
  "accuracy": null
}
```

| Field | Required | Notes |
|---|---|---|
| `trigger_type` | No | `"iot_button"` for wearable, `"manual"` for in-app button. Defaults to `"manual"`. Any string is accepted. |
| `latitude` | No | Defaults to `0.0` if omitted or ESP32 (no GPS) sends null |
| `longitude` | No | Defaults to `0.0` |
| `accuracy` | No | `null` accepted — ESP32 has no GPS. Field is silently ignored by the backend. |

**Extra/unknown fields are silently ignored.** This is intentional — the ESP32 payload may evolve without breaking the endpoint.

**Response — 201 Created**
```json
{
  "success": true,
  "message": "SOS countdown started",
  "data": {
    "alert_id": "uuid-string",
    "trigger_type": "iot_button",
    "address": null,
    "status": "countdown",
    "triggered_at": "2026-03-11T10:15:00+05:30",
    "sent_at": null,
    "resolved_at": null,
    "resolution_type": null,
    "timezone": "Asia/Kolkata",
    "countdown_seconds": 10,
    "contacts_to_notify": 3
  }
}
```

| Response field | Purpose |
|---|---|
| `alert_id` | Store this — required for cancel, send-now, safe calls |
| `countdown_seconds` | How long the cancellation window is (from server config). App should use this, not a hardcoded value. |
| `contacts_to_notify` | Show in countdown UI: "Notifying 3 contacts in 10s" |
| `trigger_type` | `"iot_button"` — confirms the source |

**Error Responses**

| HTTP | code | When |
|---|---|---|
| `400` | `NO_CONTACTS` | User has no emergency contacts saved |
| `400` | `VALIDATION_ERROR` | Schema validation failure |
| `400` | `ERROR` | Cooldown active or other business logic failure |

**Cooldown behaviour:** After a trigger, there is a 20-second cooldown on manual/IoT triggers (`SOS_COOLDOWN_SECONDS`). A second trigger during cooldown returns the existing countdown alert with a warning message.

---

### 5.2 POST /api/sos/cancel

Cancels an active SOS. Called by `IotSosTracker` on double-tap detection, or manually from in-app cancel button.

**Request**
```json
{
  "alert_id": "uuid-string"
}
```

**Response — 200 OK**
```json
{
  "success": true,
  "message": "SOS Cancelled",
  "data": null
}
```

**Error Responses**

| HTTP | code | When | App action |
|---|---|---|---|
| `400` | `VALIDATION_ERROR` | Missing `alert_id` | Check call site |
| `400` | `ALREADY_RESOLVED` | Alert was already cancelled or resolved | Log warning — do nothing, tracker auto-resets |
| `401` | `UNAUTHORIZED` | `alert_id` belongs to a different user | Should not happen — log and investigate |
| `404` | `ALERT_NOT_FOUND` | `alert_id` doesn't exist (stale ID, server restart) | Log warning — tracker auto-resets its state |

**State restriction:** Cancel only succeeds on alerts with status `countdown` or `sent`. Attempting to cancel an already `cancelled` or `resolved` alert returns `400 ALREADY_RESOLVED`.

---

### 5.3 POST /api/sos/safe

Mark the user as safe. Called when the user explicitly marks false alarm from the app UI after the SOS has been sent. Sends WhatsApp "I'm safe" notification to all contacts if the alert was already dispatched (`sent` status).

**Request**
```json
{
  "alert_id": "uuid-string"
}
```

**Response — 200 OK**
```json
{
  "success": true,
  "message": "Safe notification sent to 3 contact(s)",
  "data": {
    "alert_id": "uuid-string",
    "trigger_type": "iot_button",
    "status": "cancelled",
    "resolution_type": "false_alarm",
    "triggered_at": "2026-03-11T10:15:00+05:30",
    "resolved_at": "2026-03-11T10:16:30+05:30",
    "contacts_notified": 3,
    "timezone": "Asia/Kolkata"
  }
}
```

**Key behaviour:**
- If the alert was in `countdown` state (never dispatched) → sets `cancelled` / `false_alarm`, notifies 0 contacts.
- If the alert was in `sent` state (already dispatched) → sets `cancelled` / `false_alarm`, sends WhatsApp safe notification to all contacts.

**Error Responses**

| HTTP | code | When |
|---|---|---|
| `400` | `VALIDATION_ERROR` | Missing `alert_id` |
| `400` | `ALREADY_RESOLVED` | Alert already cancelled/resolved |
| `401` | `UNAUTHORIZED` | Alert belongs to different user |
| `404` | `ALERT_NOT_FOUND` | `alert_id` not found |

---

### 5.4 POST /api/sos/send-now

Skip the countdown timer and dispatch the SOS immediately. This is called by the app's countdown screen when the user taps "Send Now" or when the countdown timer expires.

**Request**
```json
{
  "alert_id": "uuid-string"
}
```

**Response — 200 OK**
```json
{
  "success": true,
  "message": "SOS Dispatched via WhatsApp",
  "delivery_report": [
    {
      "phone": "+919876543210",
      "success": true,
      "status": "sent",
      "error_code": null,
      "error_msg": null
    }
  ]
}
```

**Error Responses**

| HTTP | code | When |
|---|---|---|
| `400` | `VALIDATION_ERROR` | Missing `alert_id` |
| `400` | `ERROR` | Alert already resolved/cancelled, or invalid state |

---

### 5.5 GET /api/sos/history

Returns all past SOS alerts for the authenticated user, including IoT-triggered ones, sorted newest first.

**Request** — no body

**Response — 200 OK**
```json
{
  "success": true,
  "data": [
    {
      "alert_id": "uuid-string",
      "trigger_type": "iot_button",
      "address": "12 Main St, Kolkata",
      "status": "cancelled",
      "triggered_at": "2026-03-11T10:15:00+05:30",
      "sent_at": null,
      "resolved_at": "2026-03-11T10:15:45+05:30",
      "resolution_type": "cancelled",
      "timezone": "Asia/Kolkata"
    }
  ]
}
```

`trigger_type` is included in every history item — the UI can show "Wearable button" vs "Manual" labels.

---

## 6. SOS State Machine

```
                    POST /sos/trigger
                         │
                         ▼
                    ┌──────────┐
                    │countdown │  ← app shows cancel button + countdown timer
                    └──────────┘
                    /          \
                   /            \
   POST /sos/cancel         POST /sos/send-now
   (double-tap or           (timer expired or
    in-app cancel)           user taps Send Now)
          │                        │
          ▼                        ▼
     ┌──────────┐            ┌──────────┐
     │cancelled │            │   sent   │  ← WhatsApp dispatched
     └──────────┘            └──────────┘
                                  │
                        POST /sos/safe
                        (user is safe)
                                  │
                                  ▼
                            ┌──────────┐
                            │cancelled │  resolution_type = false_alarm
                            └──────────┘
```

**Rules:**
- `cancel` works on `countdown` and `sent`.
- `safe` works on `countdown` and `sent`.
- Calling `cancel` or `safe` on an already-`cancelled` or `resolved` alert → `400 ALREADY_RESOLVED`.
- A stale `alert_id` (e.g. after server restart) → `404 ALERT_NOT_FOUND`.

---

## 7. Service Layer Changes

### `app/services/sos_service.py`

#### `trigger_sos(user_id, lat, lng, trigger_type='manual')`
- Accepts any string for `trigger_type`, including `"iot_button"`.
- On duplicate: auto-cancels stale `countdown` alerts older than 60 seconds.
- Returns `(SOSAlert, message_str)`.

#### `cancel_sos(alert_id, user_id=None)`
- **Fixed:** Previously allowed cancelling `sent` and `countdown` alerts via a silent `pass` on the `sent` branch. Now checks status first:
  - If `cancelled` or `resolved` → returns `(False, "This alert has already been resolved (status: ...)")`.
  - If `countdown` or `sent` → cancels and returns `(True, "SOS Cancelled")`.
- Returns `(bool, str)`.

#### `mark_user_safe(alert_id, user_id)`
- Accepts `countdown` and `sent` states.
- If `countdown` → cancels with no WhatsApp notification (never dispatched).
- If `sent` → cancels and sends WhatsApp safe notification to all contacts.
- Returns `(bool, str, contacts_notified: int)`.

#### `dispatch_sos(alert_id, user_id=None)`
- Moves alert from `countdown` → `sent`.
- Sends WhatsApp message to all trusted contacts.
- Returns `(bool, message_str, delivery_report[])`.

---

## 8. Schema / Validation Changes

### `SOSTriggerSchema` (`app/routes/sos.py`)

```python
class SOSTriggerSchema(Schema):
    latitude     = fields.Float(load_default=0.0)
    longitude    = fields.Float(load_default=0.0)
    trigger_type = fields.Str(load_default='manual')
    accuracy     = fields.Float(allow_none=True, load_default=None)  # ← added

    class Meta:
        unknown = EXCLUDE  # ← added: silently drops unknown fields
```

**Why `accuracy`?** The Android app sends `"accuracy": null` in the IoT path because the ESP32 has no GPS. Without the explicit field declaration, marshmallow 3 (which rejects unknown fields by default) would return `400 VALIDATION_ERROR` on every IoT SOS trigger.

**Why `EXCLUDE`?** Keeps the endpoint stable as the app payload evolves. Any unknown field is silently dropped rather than rejected.

### `DeviceRegisterSchema` (`app/routes/device.py`)

```python
class DeviceRegisterSchema(Schema):
    device_name      = fields.Str(required=True)
    device_mac       = fields.Str(required=True)
    firmware_version = fields.Str(allow_none=True, load_default=None)

    class Meta:
        unknown = EXCLUDE  # ← added
```

### `ButtonEventSchema` (`app/routes/device.py`)

```python
class ButtonEventSchema(Schema):
    device_mac = fields.Str(required=True)
    latitude   = fields.Float(load_default=0.0)
    longitude  = fields.Float(load_default=0.0)

    class Meta:
        unknown = EXCLUDE  # ← added
```

---

## 9. Configuration Variables

All configurable via environment variables, with sensible defaults.

| Variable | Default | Description |
|---|---|---|
| `SOS_COUNTDOWN_SECONDS` | `10` | Countdown duration in seconds. Returned in `/sos/trigger` response as `countdown_seconds`. App reads this — do not hardcode on the app side. |
| `SOS_COOLDOWN_SECONDS` | `20` | Minimum seconds between manual/IoT SOS triggers per user. |
| `IOT_DOUBLE_TAP_WINDOW_SECONDS` | `1.5` | Used only by the legacy `/device/button-event` endpoint. The Android `IotSosTracker` has its own configurable window. |
| `JWT_SOS_TOKEN_EXPIRES_DAYS` | `30` | Long-lived SOS token lifetime. This token is used by `IotSosTracker` for the `/sos/trigger` call so alerts work even if the regular access token has expired. |

---

## 10. Error Code Reference

### Standard error response shape

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE_STRING",
    "message": "Human-readable description"
  }
}
```

### All error codes

| Code | HTTP | Meaning | Produced by |
|---|---|---|---|
| `VALIDATION_ERROR` | 400 | Request body failed schema validation | All endpoints |
| `NO_CONTACTS` | 400 | User has no trusted contacts | `/sos/trigger` |
| `ERROR` | 400 | Generic business logic failure | Multiple |
| `ALREADY_RESOLVED` | 400 | Cancel/safe on already-resolved alert | `/sos/cancel`, `/sos/safe` |
| `UNAUTHORIZED` | 401 | `alert_id` or `device_id` belongs to another user | SOS + device endpoints |
| `ALERT_NOT_FOUND` | 404 | Stale or unknown `alert_id` | `/sos/cancel`, `/sos/safe` |
| `NOT_FOUND` | 404 | Device not found or wrong owner | Device endpoints |

---

## 11. End-to-End IoT SOS Flow

### Normal trigger → countdown → send flow

```
User presses wearable button
        │
        ▼ (BLE frame: "SOS_TRIGGER_RANDOM_MESSAGE")
Android IotSosTracker detects single-tap
        │
        ▼
POST /api/sos/trigger
{
  "latitude": 22.5726,
  "longitude": 88.3639,
  "trigger_type": "iot_button",
  "accuracy": null
}
        │
        ▼ 201 Created
{
  "data": {
    "alert_id": "abc-123",
    "status": "countdown",
    "countdown_seconds": 10,
    "contacts_to_notify": 2,
    "trigger_type": "iot_button"
  }
}
        │
        ▼ App stores alert_id, starts 10s countdown timer
        │
    [10 seconds pass, user does not cancel]
        │
        ▼
POST /api/sos/send-now  { "alert_id": "abc-123" }
        │
        ▼ 200 OK — WhatsApp sent to all contacts
        │
User is found safe
        │
        ▼
POST /api/sos/safe  { "alert_id": "abc-123" }
        │
        ▼ 200 OK — "I'm safe" WhatsApp sent to all contacts
```

### Double-tap cancel flow

```
User presses button twice within 1.5s
        │
        ▼ (two BLE frames arrive in app within tap window)
Android IotSosTracker detects double-tap
        │
        ▼
POST /api/sos/cancel  { "alert_id": "abc-123" }
        │
        ▼ 200 OK — alert cancelled, no WhatsApp sent
```

### Stale alert_id (server restart / re-launch) flow

```
IotSosTracker has stored alert_id from previous session
        │
        ▼
POST /api/sos/cancel  { "alert_id": "old-uuid" }
        │
        ▼ 404 ALERT_NOT_FOUND
        │
App clears stored alert_id and resets tracker state
```

---

## 12. What Was Done — Change Log

### Phase 1 — DB Foundation

| Change | File | Status |
|---|---|---|
| Added `last_button_press_at` column to `connected_devices` | migration `c1d2e3f4g5h6` | ✅ Applied to PostgreSQL |
| Added `iot_button` to `trigger_type_enum` in PostgreSQL | migration `c1d2e3f4g5h6` | ✅ Applied to PostgreSQL |

### Phase 2 — Architecture Pivot (app-side tap detection)

The original design had the backend detect double-taps via `/api/device/button-event`. This was changed so the Android app (`IotSosTracker`) owns all tap logic and calls the standard SOS endpoints directly.

| Change | File | Status |
|---|---|---|
| `/button-event` endpoint retained but superseded | `app/routes/device.py` | ✅ Legacy, not called in new flow |
| `IotSosTracker` calls `/sos/trigger` with `trigger_type: "iot_button"` | Android (not in this repo) | ✅ Contract defined |

### Phase 3 — Critical Bug Fix (marshmallow 3 compatibility)

| Bug | Fix | File |
|---|---|---|
| `"accuracy": null` caused `400 VALIDATION_ERROR` on every IoT SOS trigger because marshmallow 3 rejects unknown fields by default | Added `accuracy = fields.Float(allow_none=True, load_default=None)` + `class Meta: unknown = EXCLUDE` | `app/routes/sos.py` |
| `missing=` kwarg deprecated in marshmallow 3 | Replaced all `missing=` with `load_default=` | `app/routes/sos.py` |

### Phase 4 — Contract Compliance Fixes

| Gap | Fix | File |
|---|---|---|
| `cancel()` returned `"ERROR"` for all failures | Now returns `ALERT_NOT_FOUND` (404), `ALREADY_RESOLVED` (400), `UNAUTHORIZED` (401) | `app/routes/sos.py` |
| `cancel_sos()` silently allowed double-cancel via `if alert.status == 'sent': pass` fall-through | Added explicit check: if `cancelled` or `resolved` → return error | `app/services/sos_service.py` |
| `GET /device/status` returned `404` when no device paired | Now returns `200 + {"data": null}` | `app/routes/device.py` |
| `PUT /device/{id}/status` only updated `last_seen` on connect, not disconnect | `last_seen` now always updated unconditionally | `app/routes/device.py` |
| `to_dict()` missing `device_mac` and `signal_strength` fields required by Android DTO | Both added (`signal_strength` reserved as `null`) | `app/models/device.py` |
| `DeviceRegisterSchema` and `ButtonEventSchema` rejected unknown fields | Added `class Meta: unknown = EXCLUDE` to both | `app/routes/device.py` |
| `EXCLUDE` not imported in `device.py` | Added to marshmallow import line | `app/routes/device.py` |

---

*This document reflects the state of the backend as of 11 March 2026. For the full contract between Android and backend, see [IOT_WEARABLE_BACKEND_CONTRACT.md](IOT_WEARABLE_BACKEND_CONTRACT.md). For Android implementation guidance, see [IOT_WEARABLE_ANDROID_GUIDE.md](IOT_WEARABLE_ANDROID_GUIDE.md).*
