# IoT Wearable — Android Team: Backend Response Contract

> **Audience:** Asfalis Android app team  
> **Date:** 11 March 2026  
> **Companion docs:** `IOT_WEARABLE_ANDROID_GUIDE.md`, `IOT_WEARABLE_BACKEND_CONTRACT.md`

This document captures **exactly what the backend returns** for each SOS endpoint used by the IoT wearable flow. Several details differ from the simplified shapes shown in the backend contract — this is the ground truth for writing Kotlin data classes and Retrofit adapters.

---

## ⚠️ Critical Differences From the Contract Doc

### 1. Top-level envelope uses `"success"` (Boolean), NOT `"status"` (String)

The contract shows:
```json
{ "status": "success", "data": { ... } }
```

The backend **actually** returns:
```json
{ "success": true, "data": { ... }, "message": "..." }
```

**Kotlin fix** — use `success: Boolean`, not `status: String`:

```kotlin
// ❌ WRONG — based on contract doc
data class SosTriggerResponse(val status: String, val data: SosTriggerData?)

// ✅ CORRECT — matches actual backend
data class SosTriggerResponse(
    val success: Boolean,
    val message: String,
    val data: SosTriggerData?
)
```

---

### 2. Error shape — nested under `"error"` key

The contract lists error codes (`ALREADY_RESOLVED`, `UNAUTHORIZED`, etc.) but not the shape.

Actual error response:
```json
{
  "success": false,
  "error": {
    "code": "ALERT_NOT_FOUND",
    "message": "Alert not found"
  }
}
```

**Kotlin models:**
```kotlin
data class ApiError(val code: String, val message: String)

// Generic wrapper that covers all endpoints
data class ApiResponse<T>(
    val success: Boolean,
    val message: String? = null,
    val data: T? = null,
    val error: ApiError? = null
)
```

To check for errors: `if (!response.success) handleError(response.error)`

---

## Endpoint-by-Endpoint Actual Response Shapes

### `POST /api/sos/trigger` → HTTP **201** (not 200)

```json
{
  "success": true,
  "message": "SOS countdown started",
  "data": {
    "alert_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "trigger_type": "iot_button",
    "address": null,
    "status": "countdown",
    "triggered_at": "2026-03-11T18:30:00+05:30",
    "sent_at": null,
    "resolved_at": null,
    "resolution_type": null,
    "timezone": "Asia/Kolkata",
    "countdown_seconds": 10,
    "contacts_to_notify": 2
  }
}
```

**Kotlin data class:**
```kotlin
data class SosTriggerData(
    val alert_id: String,
    val trigger_type: String,
    val address: String?,
    val status: String,            // "countdown"
    val triggered_at: String,
    val sent_at: String?,
    val resolved_at: String?,
    val resolution_type: String?,
    val timezone: String,
    val countdown_seconds: Int,    // use this to drive your countdown timer
    val contacts_to_notify: Int    // display "Alerting N contacts"
)
```

> **Note:** HTTP status is `201`, not `200`. Retrofit's `@POST` handles this fine — just ensure your `Response<T>` check uses `response.isSuccessful` (which covers 2xx) rather than `response.code() == 200`.

---

### `POST /api/sos/cancel` → HTTP **200**

```json
{
  "success": true,
  "message": "SOS Cancelled"
}
```

No `data` field. Check `success` only.

**Kotlin:**
```kotlin
data class SosCancelResponse(
    val success: Boolean,
    val message: String
)
```

---

### `POST /api/sos/safe` → HTTP **200**

```json
{
  "success": true,
  "message": "Safe notification sent to 2 contact(s)",
  "data": {
    "alert_id": "3fa85f64-...",
    "trigger_type": "iot_button",
    "status": "cancelled",
    "resolution_type": "false_alarm",
    "contacts_notified": 2
  }
}
```

> `message` contains the exact count of WhatsApp notifications dispatched — useful for logging.

**Kotlin:**
```kotlin
data class SosSafeData(
    val alert_id: String,
    val trigger_type: String,
    val status: String,
    val resolution_type: String?,
    val contacts_notified: Int
)

data class SosSafeResponse(
    val success: Boolean,
    val message: String,
    val data: SosSafeData?
)
```

---

### `POST /api/device/register` → HTTP **201**

```json
{
  "success": true,
  "data": {
    "device_id": "uuid-string",
    "device_name": "ESP32_SOS_DEVICE",
    "is_connected": true,
    "battery_level": null,
    "firmware_version": "1.0.0",
    "last_seen": "2026-03-11T18:30:00",
    "last_button_press_at": null
  }
}
```

Persist `data.device_id` — needed for `PUT /api/device/<device_id>/status` on disconnect.

---

## Common Error Responses

| Scenario | HTTP | `error.code` | `error.message` (example) |
|---|---|---|---|
| No trusted contacts | 400 | `NO_CONTACTS` | "You must add at least one emergency contact..." |
| SOS cooldown active | 400 | `ERROR` | "SOS on cooldown — please wait 18s..." |
| Alert already cancelled | 400 | `ALREADY_RESOLVED` | "This alert has already been resolved..." |
| Access token expired | 401 | `TOKEN_EXPIRED` | "Your session has expired. Please refresh your token." |
| Token missing | 401 | `UNAUTHORIZED` | "Authentication token is required." |
| Alert not found | 404 | `ALERT_NOT_FOUND` | "Alert not found" |

---

## Retrofit Interface — Corrected Version

```kotlin
interface AsfalisApiService {

    @POST("api/sos/trigger")
    suspend fun triggerSos(@Body body: SosTriggerRequest): Response<SosTriggerResponse>
    // HTTP 201 on success — use response.isSuccessful, not response.code() == 200

    @POST("api/sos/cancel")
    suspend fun cancelSos(@Body body: SosCancelRequest): Response<SosCancelResponse>

    @POST("api/sos/safe")
    suspend fun markSafe(@Body body: SosSafeRequest): Response<SosSafeResponse>

    @POST("api/device/register")
    suspend fun registerDevice(@Body body: DeviceRegisterRequest): Response<DeviceRegisterResponse>

    @PUT("api/device/{deviceId}/status")
    suspend fun updateDeviceStatus(
        @Path("deviceId") deviceId: String,
        @Body body: DeviceStatusRequest   // { "is_connected": false }
    ): Response<GenericResponse>
}

// --------------------------------------------------------
// Request bodies
// --------------------------------------------------------

data class SosTriggerRequest(
    val trigger_type: String,   // "iot_button"
    val latitude: Double,
    val longitude: Double,
    val accuracy: Double? = null  // always null from the wearable path
)

data class SosCancelRequest(val alert_id: String)
data class SosSafeRequest(val alert_id: String)

data class DeviceRegisterRequest(
    val device_name: String,
    val device_mac: String,
    val firmware_version: String = "1.0.0"
)

data class DeviceStatusRequest(val is_connected: Boolean)
```

---

## What to Do With `IotSosTracker`

```kotlin
object IotSosTracker {
    private const val DOUBLE_TAP_WINDOW_MS = 1_500L
    private const val HARDWARE_COOLDOWN_MS = 10 * 60 * 1_000L  // 10 min
    private const val DISPATCH_CANCEL_WINDOW_MS = 60 * 1_000L  // 60 s

    private var lastPressMs: Long = 0
    private var triggeredAtMs: Long = 0
    private var dispatchedAtMs: Long = 0

    var currentAlertId: String? = null

    fun isDoubleTap(nowMs: Long): Boolean =
        lastPressMs > 0 && (nowMs - lastPressMs) < DOUBLE_TAP_WINDOW_MS

    fun recordPress(nowMs: Long) { lastPressMs = nowMs }

    fun markTriggered(nowMs: Long) { triggeredAtMs = nowMs }

    fun markDispatched(nowMs: Long) { dispatchedAtMs = nowMs }

    fun isHardwareCooldownActive(): Boolean =
        triggeredAtMs > 0 && (System.currentTimeMillis() - triggeredAtMs) < HARDWARE_COOLDOWN_MS

    /** True when SOS countdown is running (not yet dispatched). */
    fun isCountdownActive(): Boolean =
        currentAlertId != null && dispatchedAtMs == 0L

    /** True when SOS was dispatched but still within the 60-s safe-cancel window. */
    fun isRecentlyDispatched(): Boolean =
        dispatchedAtMs > 0 && (System.currentTimeMillis() - dispatchedAtMs) < DISPATCH_CANCEL_WINDOW_MS

    fun clear() {
        currentAlertId = null
        triggeredAtMs = 0
        dispatchedAtMs = 0
    }
}
```

---

## About `/api/device/button-event`

This endpoint **exists** in the backend from an earlier architecture iteration but is **not part of the current flow**. The app must **not call it** — it does server-side double-tap detection which conflicts with `IotSosTracker`. Call `/api/sos/trigger`, `/api/sos/cancel`, and `/api/sos/safe` directly as described in the Android guide.

---

*Backend questions → API team. For ESP32 firmware refer to `IOT_DEVICE_CODE.md`.*
