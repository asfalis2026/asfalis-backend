# IoT Wearable (ESP32) — Android App Integration Guide

> **Audience:** Asfalis Android app team  
> **Backend revision:** `c1d2e3f4g5h6`  
> **Date:** 2026-03-11

---

## Overview

The ESP32 wearable communicates with the phone over **Classic Bluetooth (SPP)**.  
The app acts as the bridge between the hardware and the backend:

```
[ESP32 microswitch pressed]
        │  Bluetooth SPP frame
        ▼
[Android App]
        │  HTTPS + JWT
        ▼
[Asfalis Backend]
        │
        ▼
[SOS triggered / cancelled]
```

The **app owns all press logic** — double-tap detection, cooldown enforcement, and deciding which SOS endpoint to call. The backend sees only standard SOS API calls with `trigger_type: "iot_button"` and has no knowledge of the wearable layer.

---

## Table of Contents

1. [Hardware spec](#1-hardware-spec)
2. [Step 1 — Pair & register the device](#2-step-1--pair--register-the-device)
3. [Step 2 — Listen for Bluetooth frames](#3-step-2--listen-for-bluetooth-frames)
4. [Step 3 — Forward the event to the backend](#4-step-3--forward-the-event-to-the-backend)
5. [Step 4 — React to the backend response](#5-step-4--react-to-the-backend-response)
6. [Full API reference](#6-full-api-reference)
7. [Error codes](#7-error-codes)
8. [Double-tap behaviour explained](#8-double-tap-behaviour-explained)
9. [Complete Android code example](#9-complete-android-code-example)

---

## 1. Hardware spec

| Property | Value |
|---|---|
| Device | ESP32 Dev Board |
| Bluetooth profile | Classic SPP (BluetoothSerial) |
| Device name (BT) | `ESP32_SOS_DEVICE` |
| Message sent on press | `SOS_TRIGGER_RANDOM_MESSAGE` |
| Button wiring | Microswitch COM → GND · NO → Pin 23 (`INPUT_PULLUP` — LOW on press) |
| Firmware debounce | 50 ms hardware contact-bounce filter (non-blocking, edge-triggered) |

---

## 2. Step 1 — Pair & register the device

> Do this **once** when the user first connects their wearable inside the app.

### 2a. Pair via Android Bluetooth settings
Use the standard Android Bluetooth pairing flow (`BluetoothAdapter`) to discover and pair with `ESP32_SOS_DEVICE`. Store the paired device's MAC address (e.g. `AA:BB:CC:DD:EE:FF`).

### 2b. Register with the backend

```
POST /api/device/register
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request body:**

```json
{
  "device_name": "ESP32_SOS_DEVICE",
  "device_mac": "AA:BB:CC:DD:EE:FF",
  "firmware_version": "1.0.0"
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `device_name` | string | ✅ | Human-readable label shown in the app |
| `device_mac` | string | ✅ | Bluetooth MAC in `XX:XX:XX:XX:XX:XX` format |
| `firmware_version` | string | ❌ | Optional — use `"1.0.0"` for the current build |

**Success response `201`:**

```json
{
  "success": true,
  "data": {
    "device_id": "uuid-string",
    "device_name": "ESP32_SOS_DEVICE",
    "is_connected": true,
    "battery_level": null,
    "firmware_version": "1.0.0",
    "last_seen": "2026-03-05T12:00:00",
    "last_button_press_at": null
  }
}
```

> **Persist `device_mac` in SharedPreferences** — you will send it with every button-event call.

---

## 3. Step 2 — Listen for Bluetooth frames

Open an SPP connection to the paired device and read frames in a background service / coroutine.

```kotlin
// Kotlin example — run inside a Service or coroutine
val device: BluetoothDevice = bluetoothAdapter.getRemoteDevice(savedMac)
val socket: BluetoothSocket = device.createRfcommSocketToServiceRecord(
    UUID.fromString("00001101-0000-1000-8000-00805F9B34FB") // standard SPP UUID
)
socket.connect()

val reader = BufferedReader(InputStreamReader(socket.inputStream))
while (isActive) {
    val line = reader.readLine() ?: continue
    if (line.trim() == "SOS_TRIGGER_RANDOM_MESSAGE") {
        onButtonPressed()   // see Step 3
    }
}
```

> **Keep the Bluetooth service alive as a Foreground Service** so it survives screen-off and app backgrounding.

---

## 4. Step 3 — Forward the event to the backend

Every time `SOS_TRIGGER_RANDOM_MESSAGE` is received, call the `button-event` endpoint. **Do not debounce on the app side** — the backend handles single vs. double-tap detection.

```
POST /api/device/button-event
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request body:**

```json
{
  "device_mac": "AA:BB:CC:DD:EE:FF",
  "latitude": 22.5726,
  "longitude": 88.3639
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `device_mac` | string | ✅ | Must match the MAC registered in Step 1 |
| `latitude` | float | ❌ | Current GPS latitude — default `0.0` if unavailable |
| `longitude` | float | ❌ | Current GPS longitude — default `0.0` if unavailable |

> **Always send the freshest GPS fix.** The backend embeds the coordinates in the SOS alert and generates a Google Maps link from them.

---

## 5. Step 4 — React to the backend response

### After `POST /api/sos/trigger` — SOS countdown started

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

**What to do:**

- Store `alert_id` in `IotSosTracker` — needed for subsequent cancel/safe calls.
- Navigate to / show the **SOS countdown screen** (same screen as a manual SOS trigger).
- The existing countdown + "Send Now" / "I'm Safe" buttons work identically.

### After `POST /api/sos/cancel` or `POST /api/sos/safe`

```json
{ "status": "success", "data": null }
```

**What to do:**

- Show a **"SOS Cancelled"** (or "You're marked safe") `Toast` or `Snackbar`.
- If the countdown screen is visible, dismiss it.
- Clear `IotSosTracker` state.

### Double-tap with no active SOS

No API call is made (handled entirely in `IotSosTracker`). Silently ignore.

---

## 6. Full API reference

### `POST /api/device/register`

Register or re-register the wearable device.

| | |
|---|---|
| **Auth** | `Bearer <access_token>` (JWT) |
| **Success** | `201` |
| **Conflict** | Device already registered to this user → updates `last_seen`, returns `201` |

---

### `POST /api/sos/trigger`

Trigger an SOS alert from the wearable (single-tap). Uses `trigger_type: "iot_button"`.

| | |
|---|---|
| **Auth** | `Bearer <access_token>` (JWT) |
| **Success** | `200` |

---

### `POST /api/sos/cancel`

Cancel an active SOS during the countdown phase (double-tap).

| | |
|---|---|
| **Auth** | `Bearer <access_token>` (JWT) |
| **Success** | `200` |

---

### `POST /api/sos/safe`

Mark the user safe after SOS has already been dispatched (double-tap, post-dispatch).

| | |
|---|---|
| **Auth** | `Bearer <access_token>` (JWT) |
| **Success** | `200` |

---

### `GET /api/device/status`

Check the current pairing/connection status of the user's device.

| | |
|---|---|
| **Auth** | `Bearer <access_token>` (JWT) |
| **Success** | `200` |
| **None paired** | `404` |

---

### `PUT /api/device/<device_id>/status`

Update `is_connected` manually (call with `false` on BT disconnect).

```json
{ "is_connected": false }
```

---

### `DELETE /api/device/<device_id>`

Remove the device pairing.

---

## 7. Error codes

| HTTP | `error_code` | App behavior |
|---|---|---|
| `400` | `VALIDATION_ERROR` | Log error; show user a generic failure toast |
| `400` | `NO_CONTACTS` | Prompt user to add an emergency contact before wearable is useful |
| `400` | `ALREADY_RESOLVED` | Log warning; SOS was already cancelled — do nothing |
| `401` | `UNAUTHORIZED` | Log error; token likely expired — user must re-login via UI |
| `404` | `ALERT_NOT_FOUND` | Log warning; stale `alert_id` in `IotSosTracker` — auto-resolve tracker state |
| `5xx` | Any | Log error; no retry — user sees no feedback |

---

## 8. Double-tap behaviour explained

All timing logic lives in `IotSosTracker` on the Android side. The backend has no knowledge of double-tap semantics.

The firmware emits one `SOS_TRIGGER_RANDOM_MESSAGE` per falling edge after a 50 ms hardware debounce. The app measures the gap between successive events:

```
Frame received from ESP32
    │
    ├─ gap from last frame ≥ 1 500 ms  (or first ever press)
    │       → SINGLE TAP
    │           ├─ cooldown active?  → no API call
    │           └─ no cooldown?      → POST /api/sos/trigger  (trigger_type: "iot_button")
    │
    └─ gap from last frame < 1 500 ms
            → DOUBLE TAP
                ├─ SOS in countdown?    → POST /api/sos/cancel
                ├─ SOS dispatched <60s? → POST /api/sos/safe
                └─ no active SOS?       → no API call
```

> The 1 500 ms window and the 10-minute hardware cooldown are constants in `IotSosTracker`.

---

## 9. Complete Android code example

```kotlin
// IotWearableManager.kt

class IotWearableManager(
    private val context: Context,
    private val apiService: AsfalisApiService,   // Retrofit interface
    private val locationHelper: LocationHelper,
    private val tracker: IotSosTracker           // in-memory state singleton
) {
    private val savedMac: String
        get() = PreferenceManager
            .getDefaultSharedPreferences(context)
            .getString("iot_device_mac", "") ?: ""

    private var socket: BluetoothSocket? = null
    private var readerJob: Job? = null

    // ------------------------------------------------------------------ //
    // Step 2 — Connect & listen                                           //
    // ------------------------------------------------------------------ //
    fun startListening(scope: CoroutineScope) {
        readerJob = scope.launch(Dispatchers.IO) {
            val adapter = BluetoothAdapter.getDefaultAdapter() ?: return@launch
            val device = adapter.getRemoteDevice(savedMac)
            socket = device.createRfcommSocketToServiceRecord(
                UUID.fromString("00001101-0000-1000-8000-00805F9B34FB")
            )
            socket!!.connect()

            val reader = BufferedReader(InputStreamReader(socket!!.inputStream))
            while (isActive) {
                val line = reader.readLine() ?: break
                if (line.trim() == "SOS_TRIGGER_RANDOM_MESSAGE") {
                    handleButtonPress(scope)
                }
            }
        }
    }

    // ------------------------------------------------------------------ //
    // Step 3 — App-side press logic + backend call                       //
    // ------------------------------------------------------------------ //
    private fun handleButtonPress(scope: CoroutineScope) {
        val now = System.currentTimeMillis()
        val isDoubleTap = tracker.isDoubleTap(now)  // gap < 1500 ms
        tracker.recordPress(now)

        scope.launch {
            val location = locationHelper.getLastKnownLocation()
            try {
                if (isDoubleTap) {
                    // Double-tap — cancel or mark safe
                    val alertId = tracker.currentAlertId
                    if (alertId == null) return@launch  // no active SOS — ignore
                    if (tracker.isCountdownActive()) {
                        apiService.cancelSos(SosCancelRequest(alert_id = alertId))
                        withContext(Dispatchers.Main) {
                            Toast.makeText(context, "SOS Cancelled", Toast.LENGTH_SHORT).show()
                            NavigationManager.dismissSosCountdown()
                        }
                    } else if (tracker.isRecentlyDispatched()) {
                        apiService.markSafe(SosSafeRequest(alert_id = alertId))
                        withContext(Dispatchers.Main) {
                            Toast.makeText(context, "You're marked safe", Toast.LENGTH_SHORT).show()
                            NavigationManager.dismissSosCountdown()
                        }
                    }
                    tracker.clear()
                } else {
                    // Single tap — trigger SOS (respect cooldown)
                    if (tracker.isHardwareCooldownActive()) return@launch
                    val response = apiService.triggerSos(
                        SosTriggerRequest(
                            trigger_type = "iot_button",
                            latitude     = location?.latitude  ?: 0.0,
                            longitude    = location?.longitude ?: 0.0,
                            accuracy     = null
                        )
                    )
                    tracker.currentAlertId = response.data?.alert_id
                    tracker.markTriggered()
                    withContext(Dispatchers.Main) {
                        NavigationManager.openSosCountdown()
                    }
                }
            } catch (e: HttpException) {
                when (e.code()) {
                    400 -> Log.w(TAG, "SOS already resolved or bad request: ${e.message()}")
                    401 -> Log.e(TAG, "Unauthorized — user must re-login")
                    404 -> { Log.w(TAG, "Stale alert_id"); tracker.clear() }
                    else -> Log.e(TAG, "Server error: ${e.code()}")
                }
            }
        }
    }

    fun stopListening() {
        readerJob?.cancel()
        socket?.close()
    }

    companion object { private const val TAG = "IotWearableManager" }
}

// ------------------------------------------------------------------ //
// Retrofit request / response models                                  //
// ------------------------------------------------------------------ //

data class SosTriggerRequest(
    val trigger_type: String,   // always "iot_button"
    val latitude: Double,
    val longitude: Double,
    val accuracy: Double?
)

data class SosTriggerResponse(
    val status: String,
    val data: SosTriggerData?
)

data class SosTriggerData(
    val alert_id: String,
    val status: String,
    val countdown_seconds: Int,
    val contacts_to_notify: Int
)

data class SosCancelRequest(val alert_id: String)
data class SosSafeRequest(val alert_id: String)

// ------------------------------------------------------------------ //
// Retrofit interface additions                                        //
// ------------------------------------------------------------------ //

interface AsfalisApiService {
    @POST("api/sos/trigger")
    suspend fun triggerSos(@Body body: SosTriggerRequest): SosTriggerResponse

    @POST("api/sos/cancel")
    suspend fun cancelSos(@Body body: SosCancelRequest): GenericSosResponse

    @POST("api/sos/safe")
    suspend fun markSafe(@Body body: SosSafeRequest): GenericSosResponse

    @POST("api/device/register")
    suspend fun registerDevice(@Body body: DeviceRegisterRequest): DeviceRegisterResponse
}
```

---

## Quick checklist

- [ ] Request `BLUETOOTH`, `BLUETOOTH_ADMIN`, `BLUETOOTH_CONNECT`, `BLUETOOTH_SCAN` permissions in `AndroidManifest.xml`
- [ ] Run the Bluetooth listener as a **Foreground Service** with a persistent notification
- [ ] Call `POST /api/device/register` once during wearable onboarding and save the `device_mac` in SharedPreferences (registration failure is non-fatal — BT connection starts regardless)
- [ ] Implement `IotSosTracker` to track: last-press timestamp, double-tap window (1 500 ms), 10-min hardware cooldown, 60-s post-dispatch cancel window, and current `alert_id`
- [ ] On `SOS_TRIGGER_RANDOM_MESSAGE` single-tap → `POST /api/sos/trigger` with `trigger_type: "iot_button"`
- [ ] On `SOS_TRIGGER_RANDOM_MESSAGE` double-tap (countdown) → `POST /api/sos/cancel`
- [ ] On `SOS_TRIGGER_RANDOM_MESSAGE` double-tap (post-dispatch) → `POST /api/sos/safe`
- [ ] On Bluetooth disconnect → call `PUT /api/device/<device_id>/status` with `{ "is_connected": false }`
- [ ] Handle `NO_CONTACTS` (400): prompt user to add an emergency contact before the wearable is useful
- [ ] Handle `UNAUTHORIZED` (401): log error, user must re-login via UI
- [ ] Handle `ALERT_NOT_FOUND` (404): log warning and clear `IotSosTracker` state

---

*For backend questions contact the API team. For hardware questions refer to the ESP32 setup doc.*
