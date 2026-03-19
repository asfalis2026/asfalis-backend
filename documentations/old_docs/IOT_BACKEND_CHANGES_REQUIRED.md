# IoT Wearable — Backend Changes Required

> **Date:** 11 March 2026
> **Audience:** Asfalis Backend team
> **Source of truth:** `IOT_WEARABLE_BACKEND_CONTRACT.md` (full API contract)
> **Frontend DTOs verified from:** `data/network/dto/SosDtos.kt`, `data/network/dto/DeviceSupportDtos.kt`

---

## TL;DR

No new endpoints. No new database tables. No migrations.

The IoT wearable integration reuses the existing SOS and device registration APIs entirely.
All changes on the backend are confined to:

1. **Schema validation** — accept `accuracy: null` and the new `trigger_type` value
2. **Allowlist extension** — add `"iot_button"` to `trigger_type`
3. **Response field confirmation** — four specific fields that the app reads
4. **`/api/sos/safe` state acceptance** — must handle `countdown` AND `sent` status
5. **Device disconnect callback** — `PUT /api/device/{id}/status` must be functional

---

## 1 — Endpoint Inventory (All Endpoints the App Now Calls)

The Android app calls the following endpoints as part of the wearable integration. Every endpoint here must be reachable and return the exact shape described in §3.

| Method | Path | Called when |
|--------|------|-------------|
| `POST` | `/api/device/register` | App pairs with ESP32 for the first time |
| `GET` | `/api/device/status` | App checks connection state on resume |
| `PUT` | `/api/device/{id}/status` | ESP32 disconnects (BT drops or app closes) |
| `DELETE` | `/api/device/{id}` | User unpairs the wearable in settings |
| `POST` | `/api/sos/trigger` | Single button press (iot_button trigger) |
| `POST` | `/api/sos/cancel` | Double tap during countdown phase |
| `POST` | `/api/sos/safe` | Double tap within 60 s of dispatch |
| `POST` | `/api/sos/send-now` | User taps "Send Now" on the SOS countdown screen *(not a wearable call — included for completeness)* |
| `GET` | `/api/sos/history` | SOS history screen — must return `trigger_type` per record |

**NOT called (dead endpoint — leave in place but it is not part of the new flow):**
```
POST /api/device/button-event   ← DO NOT call from the new flow
```

---

## 2 — Schema / Validation Changes

### 2.1 `POST /api/sos/trigger` — New field: `trigger_type: "iot_button"`

**Add `"iot_button"` to the `trigger_type` allowlist** alongside existing values:

| Value | Source |
|-------|--------|
| `"manual"` | User taps the in-app SOS button |
| `"auto"` | Accelerometer / inactivity auto-SOS |
| `"iot_button"` | **NEW** — ESP32 hardware wearable button |

The backend must **persist** `trigger_type` in the SOS alert record. `GET /api/sos/history` already returns it — confirm the stored value is used there.

---

### 2.2 `POST /api/sos/trigger` — Nullable `accuracy` field

The Android app always sends `"accuracy": null` from the wearable path (the phone does not have accuracy metadata when the button is pressed):

```json
{
  "trigger_type": "iot_button",
  "latitude": 22.5726,
  "longitude": 88.3639,
  "accuracy": null
}
```

**If the backend uses marshmallow 3 (default behavior rejects unknown/null fields):**

```python
class SOSTriggerSchema(Schema):
    trigger_type = fields.Str(required=True, validate=validate.OneOf(["manual", "auto", "iot_button"]))
    latitude     = fields.Float(required=True)
    longitude    = fields.Float(required=True)
    accuracy     = fields.Float(load_default=None, allow_none=True)   # ← must be explicit + allow_none

    class Meta:
        unknown = EXCLUDE   # ← must be set — marshmallow 3 raises on unknown fields by default
```

**If the backend uses Pydantic:**

```python
class SOSTriggerRequest(BaseModel):
    trigger_type : Literal["manual", "auto", "iot_button"]
    latitude     : float
    longitude    : float
    accuracy     : Optional[float] = None   # ← Optional + None default
```

---

### 2.3 `POST /api/device/register` — Request body

The app sends:

```json
{
  "device_name": "ESP32_SOS_DEVICE",
  "device_mac": "AA:BB:CC:DD:EE:FF",
  "firmware_version": "1.0.0"
}
```

`firmware_version` is nullable on the Android side (`String? = null`) — accept it as optional.
The response **must** include `data.device_id` — this is stored on the phone and used by
`PUT /api/device/{id}/status` on every disconnect.

---

### 2.4 `PUT /api/device/{id}/status` — Request body

Called when the BT connection drops (device powers off, goes out of range, or app is killed):

```json
{
  "is_connected": false
}
```

This is a simple status update. The `{id}` path parameter is the `device_id` returned by
`POST /api/device/register`. If the backend marks this path as authenticated,
the JWT at disconnect time may be stale — consider accepting a 15-minute grace window
or using the `device_mac` as a secondary lookup.

---

## 3 — Response Contract (Exact Shapes the App Deserializes)

All responses use this envelope — `"success"` is a `Boolean`, **not** a `"status"` string:

```json
{
  "success": true | false,
  "data": { ... } | null,
  "error": { "code": "...", "message": "..." }   // only when success=false
}
```

### 3.1 `POST /api/sos/trigger` → HTTP 201

```json
{
  "success": true,
  "data": {
    "alert_id":          "abc123",
    "status":            "countdown",
    "countdown_seconds": 10,
    "contacts_to_notify": 3
  }
}
```

| Field | Type | Notes |
|-------|------|-------|
| `alert_id` | `String` | **Required** — stored in `IotSosTracker`, used by cancel/safe |
| `status` | `String` | **Required** — must be `"countdown"` on trigger |
| `countdown_seconds` | `Int` | **Required** — drives the on-screen timer; app fallback is 10 if missing |
| `contacts_to_notify` | `Int` | **Required** — displayed in UI; app fallback is 0 if missing |

> ⚠️ Although the Android DTO declares `countdown_seconds` and `contacts_to_notify` as nullable
> (`Int?`) with fallback defaults, the backend **must always send both fields**.
> Omitting them silently hides the countdown timer and contact count from the user.

---

### 3.2 `POST /api/sos/cancel` → HTTP 200

```json
{
  "success": true,
  "data": null
}
```

The app checks `response.isSuccessful` only. No fields are read from `data`.

---

### 3.3 `POST /api/sos/safe` → HTTP 200

```json
{
  "success": true,
  "data": null
}
```

**Critical:** This endpoint must accept alerts in **both** states:
- `"countdown"` — user hasn't yet sent; double-tap immediately after single-tap before countdown ends
- `"sent"` — alert already dispatched; double-tap within 60 seconds of dispatch

If the backend currently restricts `/api/sos/safe` to `"sent"` state only, it must also allow `"countdown"` state (or treat it identically to a cancel-then-safe sequence).

---

### 3.4 `POST /api/device/register` → HTTP 201 *(see §4.1)*

```json
{
  "success": true,
  "data": {
    "device_id":        "uuid-string",
    "device_name":      "ESP32_SOS_DEVICE",
    "device_mac":       "AA:BB:CC:DD:EE:FF",
    "is_connected":     false,
    "battery_level":    null,
    "firmware_version": "1.0.0",
    "signal_strength":  null,
    "last_seen":        null
  }
}
```

`device_id` is **required**. All other fields except `device_name` and `is_connected` are optional
(they are declared `String?` / `Int?` in the Android DTO and will be `null` on first registration).

---

### 3.5 `GET /api/sos/history` → HTTP 200

Each item in the history list **must include `trigger_type`**:

```json
{
  "success": true,
  "data": [
    {
      "alert_id":     "abc123",
      "trigger_type": "iot_button",
      "address":      "22 Camac St, Kolkata",
      "status":       "resolved",
      "triggered_at": "2026-03-11T10:00:00Z",
      "resolved_at":  "2026-03-11T10:05:00Z"
    }
  ]
}
```

`address` and `resolved_at` are nullable. `trigger_type` is **required** — the Android DTO maps it
directly to `SosHistoryItem.triggerType` with `@SerializedName("trigger_type")`.

---

## 4 — Notes on HTTP Status Codes

### 4.1 `POST /api/device/register` — 200 vs 201

The frontend notes state HTTP **201** for device register. The backend contract checklist says
the endpoint "returns `200`". There is a mismatch.

**Functional impact:** None — the Android app uses `response.isSuccessful`, which covers all
2xx codes (200–299). Both 200 and 201 work correctly.

**Recommendation:** Standardise to **201** for any `POST` that creates a new resource.
This aligns with REST convention and matches `POST /api/sos/trigger` (also 201).

---

### 4.2 Other status codes

| Endpoint | Expected HTTP status |
|----------|----------------------|
| `POST /api/sos/trigger` | **201** |
| `POST /api/sos/cancel` | **200** |
| `POST /api/sos/safe` | **200** |
| `POST /api/sos/send-now` | **200** |
| `GET /api/sos/history` | **200** |
| `POST /api/device/register` | **201** *(recommended)* |
| `GET /api/device/status` | **200** |
| `PUT /api/device/{id}/status` | **200** |
| `DELETE /api/device/{id}` | **200** |

---

## 5 — Error Codes the Android App Handles

All error responses must use this shape — **never** put `code` at the top level:

```json
{
  "success": false,
  "error": {
    "code":    "ALERT_NOT_FOUND",
    "message": "Alert not found or already resolved"
  }
}
```

The app processes these error codes silently (log-only, no crash) from SOS calls:

| HTTP | `error.code` | Scenario | App behavior |
|------|-------------|----------|--------------|
| `400` | `ALREADY_RESOLVED` | Cancel/safe called on already-resolved alert | Log warning — no user feedback |
| `400` | `ERROR` | SOS trigger while one is already active / rate limited | Log `error.message` — `error.message` should contain the remaining wait/cooldown info |
| `400` | `NO_CONTACTS` | User has no emergency contacts when SOS is triggered | Log warning + surface UI prompt to add a contact |
| `401` | `TOKEN_EXPIRED` | JWT has expired | Log error — user re-logs in via UI |
| `401` | `UNAUTHORIZED` | Token missing from request | Log error — user re-logs in via UI |
| `404` | `ALERT_NOT_FOUND` | Stale `alert_id` in tracker (e.g. server restarted) | Log warning — tracker auto-resets its state |
| `5xx` | Any | Server-side error | Log error — no retry from the BT service |

> **Tip for `"code": "ERROR"`:** The `message` field from this response is logged by
> `IotWearableManager`. If the backend includes the remaining cooldown duration in the message
> (e.g. `"SOS on cooldown. Try again in 8 minutes."`), it will appear in logcat and can be
> surfaced in future UI iterations without a frontend schema change.

---

## 6 — What the Backend Must NOT Change

| Concern | Owner | Notes |
|---------|-------|-------|
| Double-tap detection (1 500 ms window) | Android — `IotWearableManager` | Backend has no concept of taps |
| 10-minute hardware cooldown | Android — `IotSosTracker` | In-memory only |
| 60-second "recently dispatched" safe window | Android — `IotSosTracker` | In-memory only |
| Hardware contact-bounce filter (50 ms) | ESP32 firmware | Non-blocking edge filter |
| `/api/device/button-event` endpoint | Backend (leave as-is) | Exists but is never called by the new flow — do not remove without notice |

---

## 7 — Verification Checklist

Use these test cases with Postman before marking the integration ready.

### 7.1 Schema & Allowlist

- [x] `POST /api/sos/trigger` with `"trigger_type": "iot_button"` returns `201` (not `400 VALIDATION_ERROR`)
- [x] `POST /api/sos/trigger` with `"accuracy": null` returns `201` (not `400 VALIDATION_ERROR`)
- [x] `POST /api/sos/trigger` with `"trigger_type": "iot_button"` — confirm `trigger_type` is stored and visible in GET /api/sos/history response for that alert
- [x] `POST /api/device/register` with `"firmware_version": null` (or omitted) returns success

### 7.2 Response Shape

- [x] `POST /api/sos/trigger` response body contains all 4 fields: `alert_id`, `status`, `countdown_seconds`, `contacts_to_notify`
- [x] `POST /api/sos/trigger` response `status` value is `"countdown"` (not `"active"`, `"pending"`, or any other string)
- [x] `POST /api/device/register` response body contains `data.device_id` (non-null string)
- [x] `GET /api/sos/history` response items each contain `trigger_type` field

### 7.3 State Machine

- [x] `POST /api/sos/safe` called on a `"countdown"` status alert returns `200 success: true`
- [x] `POST /api/sos/safe` called on a `"sent"` status alert returns `200 success: true`
- [x] `POST /api/sos/cancel` called twice on the same `alert_id` returns `400 ALREADY_RESOLVED` on the second call
- [x] `POST /api/sos/cancel` called with an unknown `alert_id` returns `404 ALERT_NOT_FOUND`

### 7.4 Device Lifecycle

- [x] `POST /api/device/register` → copy `data.device_id` → `PUT /api/device/{id}/status` with `{ "is_connected": false }` returns `200`
- [x] `GET /api/device/status` returns current device state for the authenticated user
- [x] `DELETE /api/device/{id}` removes the device and subsequent `GET /api/device/status` reflects no device

### 7.5 Error Codes

- [x] Trigger SOS → immediately trigger again (before cancel) → second call returns `400` with `error.code` = `"ERROR"` and a human-readable `error.message`
- [x] Trigger SOS with zero trusted contacts → returns `400 NO_CONTACTS`
- [x] Cancel with stale `alert_id` → returns `404 ALERT_NOT_FOUND`

---

## 8 — Optional (Post-Launch)

- [ ] Add `"iot_button"` label to any push notification templates or email/SMS templates that display the trigger source to the user or emergency contacts (e.g. `"Alert triggered via wearable device"` instead of `"Alert triggered via app"`)
- [ ] Consider adding `device_name` to the SOS alert record (joinable from the device table) so history can display which device originated each alert

---

## 9 — Summary of Backend Changes by Status

| Change | Status | Impact if missing |
|--------|--------|-------------------|
| Accept `trigger_type: "iot_button"` in trigger schema | ✅ Done | Every wearable SOS returns 400 — **critical** |
| Accept `accuracy: null` without validation error | ✅ Done | Every wearable SOS returns 400 — **critical** |
| Persist `trigger_type` in SOS alert record | ✅ Done | History shows wrong/missing trigger source |
| Return all 4 fields in trigger response | ✅ Done | Countdown timer not shown; contact count wrong |
| `POST /api/sos/safe` accepts `"countdown"` status | ✅ Done | Double-tap cancel during countdown fails silently |
| Return `trigger_type` in history items | ✅ Done | History UI shows no source indicator |
| `POST /api/device/register` returns `device_id` | ✅ Done | Disconnect callback (`PUT /{id}/status`) can't work |
| `PUT /api/device/{id}/status` functional | ✅ Done | Device shown as "connected" even after BT drop |
| Standardise device register to HTTP 201 | ✅ Done | No functional impact (app uses `isSuccessful`) |
| Add `"iot_button"` to notification templates | ⬜ Optional | Notification copy shows wrong trigger source |
