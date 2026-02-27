content = r"""# Asfalis Backend — Postman Testing Guide

This guide covers **every API endpoint** in the Asfalis backend, with example requests and responses.

---

## 1. Setup

### Create Environment
1. Open Postman → **Environments** → **Create Environment** ("Local").
2. Add variables:

| Variable | Value |
| :--- | :--- |
| `baseUrl` | `http://localhost:5000/api` |
| `token` | *(leave empty)* |
| `refresh_token` | *(leave empty)* |
| `sos_token` | *(leave empty)* |

3. **Save** and select "Local" from the top-right dropdown.

### Collection-Level Auth
1. Create collection **"Asfalis Backend"**.
2. Collection → **Authorization** → Type: **Bearer Token** → Token: `{{token}}`.
3. Save. All requests inherit auth automatically.

### Auto-Save Token Script
Add this to the **Tests** tab of both **Verify Phone OTP** and **Login** requests:
```javascript
var jsonData = pm.response.json();
if (jsonData.status === "success" && jsonData.data && jsonData.data.access_token) {
    pm.environment.set("token", jsonData.data.access_token);
    pm.environment.set("refresh_token", jsonData.data.refresh_token);
    pm.environment.set("sos_token", jsonData.data.sos_token);
    console.log("Tokens saved!");
}
```

---

## 2. Response Envelope

Every response follows this format:

**Success:**
```json
{
    "status": "success",
    "message": "Human readable string",
    "data": { "..." }
}
```

**Error:**
```json
{
    "status": "error",
    "error_code": "MACHINE_READABLE_CODE",
    "message": "Human readable string"
}
```

> The Android app reads `error_code` from the JSON body to handle errors programmatically.

---

## 3. Endpoints

> **Phone number format:** Always use **E.164** format `+<country_code><number>` (e.g. `+919876543210`). No spaces or dashes.

---

### Auth (`/api/auth`)

---

**1. Register (Phone)** — `POST {{baseUrl}}/auth/register/phone`

Creates the user and returns a 6-digit `otp_code`. The Android app sends this OTP to the user via native SmsManager. Tokens are **not** returned here.

Request body:
```json
{
    "full_name": "Test User",
    "phone_number": "+919876543210",
    "password": "Password123!",
    "country": "India"
}
```
Success response `201`:
```json
{
    "status": "success",
    "message": "OTP sent to phone",
    "data": {
        "phone_number": "+919876543210",
        "otp_code": "482901",
        "expires_in": 300
    }
}
```

| HTTP | `error_code` | Meaning |
|---|---|---|
| `400` | `VALIDATION_ERROR` | Missing or invalid fields |
| `409` | `CONFLICT` | Phone already registered |

---

**2. Verify Phone OTP** — `POST {{baseUrl}}/auth/verify-phone-otp`

User submits the OTP they received via SMS. Returns all 3 tokens. Run the **Auto-Save Token Script** on this request.

Request body:
```json
{
    "phone_number": "+919876543210",
    "otp_code": "482901"
}
```
Success response `200`:
```json
{
    "status": "success",
    "message": "Phone verified successfully",
    "data": {
        "user_id": "uuid",
        "full_name": "Test User",
        "phone_number": "+919876543210",
        "is_new_user": true,
        "access_token": "...",
        "refresh_token": "...",
        "sos_token": "...",
        "expires_in": 900
    }
}
```

| HTTP | `error_code` | Meaning |
|---|---|---|
| `422` | `OTP_INVALID` | Wrong or expired OTP |
| `404` | `NOT_FOUND` | Phone number not registered |

---

**3. Login (Phone)** — `POST {{baseUrl}}/auth/login/phone`

Rate-limited: 5 attempts per 15 minutes. Run the **Auto-Save Token Script** on this request.

Request body:
```json
{
    "phone_number": "+919876543210",
    "password": "Password123!"
}
```
Success response `200`:
```json
{
    "status": "success",
    "message": "Login successful",
    "data": {
        "user_id": "uuid",
        "full_name": "Test User",
        "phone_number": "+919876543210",
        "is_new_user": false,
        "access_token": "...",
        "refresh_token": "...",
        "sos_token": "...",
        "expires_in": 900
    }
}
```

| HTTP | `error_code` | Meaning |
|---|---|---|
| `401` | `UNAUTHORIZED` | Wrong password or number not found |
| `403` | `PHONE_NOT_VERIFIED` | Account exists but OTP not verified — frontend redirects to OTP screen |
| `429` | `RATE_LIMITED` | Too many login attempts |

---

**4. Resend OTP** — `POST {{baseUrl}}/auth/resend-otp`

Rate-limited: 3 requests per 15 minutes. Returns a new `otp_code` for the Android app to re-send via SMS.

Request body:
```json
{
    "phone_number": "+919876543210"
}
```
Success response `200`:
```json
{
    "status": "success",
    "message": "OTP resent",
    "data": {
        "otp_code": "739104",
        "expires_in": 300
    }
}
```

If the phone is not registered, `otp_code` will be `null` (don't reveal registration status):
```json
{
    "status": "success",
    "message": "If the number is registered, a new OTP has been generated.",
    "data": { "otp_code": null, "expires_in": 300 }
}
```

| HTTP | `error_code` | Meaning |
|---|---|---|
| `400` | `ALREADY_VERIFIED` | Phone is already verified |
| `429` | `RATE_LIMITED` | Resend limit hit |

---

**5. Forgot Password** — `POST {{baseUrl}}/auth/forgot-password`

Rate-limited: 3 requests per 15 minutes. Returns a reset OTP for the Android app to send via SMS.

Request body:
```json
{
    "phone_number": "+919876543210"
}
```
Success response `200`:
```json
{
    "status": "success",
    "message": "Password reset OTP sent",
    "data": {
        "otp_code": "201847",
        "expires_in": 300
    }
}
```

If phone not found, `otp_code` is `null`:
```json
{
    "status": "success",
    "message": "If this number exists, an OTP was sent.",
    "data": { "otp_code": null, "expires_in": 300 }
}
```

---

**6. Google Login** — `POST {{baseUrl}}/auth/google`

Currently mocked — kept for future implementation.

Request body:
```json
{
    "id_token": "google-oauth-id-token-here"
}
```

---

**7. Refresh Token** — `POST {{baseUrl}}/auth/refresh`

Implements rotation — old refresh token is revoked and a new pair is issued.

Request body:
```json
{
    "refresh_token": "{{refresh_token}}"
}
```
Success response `200`:
```json
{
    "status": "success",
    "message": "Token refreshed",
    "data": {
        "access_token": "...",
        "refresh_token": "...",
        "expires_in": 900
    }
}
```

| HTTP | `error_code` | Meaning |
|---|---|---|
| `401` | `REFRESH_TOKEN_EXPIRED` | Token expired — re-login required |
| `401` | `REFRESH_TOKEN_REUSED` | Token already used (rotation violated) |
| `401` | `REFRESH_TOKEN_INVALID` | Malformed token |

---

**8. Validate Token** — `GET {{baseUrl}}/auth/validate`

Returns `is_valid: true` if the access token in the Authorization header is valid.

Success response `200`:
```json
{
    "status": "success",
    "message": "Token is valid",
    "data": { "user_id": "uuid", "is_valid": true }
}
```

---

**9. Logout** — `POST {{baseUrl}}/auth/logout`

Request body:
```json
{
    "refresh_token": "{{refresh_token}}"
}
```
Success response `200`:
```json
{
    "status": "success",
    "message": "Logged out successfully"
}
```

---

### User (`/api/user`)

**1. Get Profile** — `GET {{baseUrl}}/user/profile`

Returns user info, trusted contacts list, protection status, and `sos_message`.

**2. Update Profile** — `PUT {{baseUrl}}/user/profile`

All fields optional — send only what you want to change.
```json
{
    "full_name": "Updated Name",
    "sos_message": "Help! I'm in danger. Please call police immediately."
}
```

**3. Update SOS Message** — `PUT {{baseUrl}}/user/sos-message`

Dedicated endpoint. Max 500 characters.
```json
{
    "sos_message": "Emergency! I need help at my current location."
}
```

**4. Update FCM Token** — `PUT {{baseUrl}}/user/fcm-token`
```json
{
    "fcm_token": "firebase-cloud-messaging-token"
}
```

**5. Delete Account (Self)** — `DELETE {{baseUrl}}/user/account`

**6. Delete User (Admin/Dev)** — `DELETE {{baseUrl}}/user/<user_id>`

---

### Contacts (`/api/contacts`)

**1. List Contacts** — `GET {{baseUrl}}/contacts`

**2. Add Contact** — `POST {{baseUrl}}/contacts`

Response includes `whatsapp_join_info` and `invite_message`. The Android app sends the invite via native share intent — no server-side email is sent.

```json
{
    "name": "Mom",
    "phone": "+919876543210",
    "relationship": "Parent",
    "is_primary": true
}
```
Success response `201`:
```json
{
    "status": "success",
    "data": {
        "id": "uuid",
        "name": "Mom",
        "phone": "+919876543210",
        "relationship": "Parent",
        "is_primary": true,
        "whatsapp_join_info": {
            "twilio_number": "+14155238886",
            "sandbox_code": "join something-popular",
            "whatsapp_link": "https://wa.me/14155238886?text=join%20something-popular"
        },
        "invite_message": "Test User added you as a trusted contact in Asfalis..."
    }
}
```

**3. Update Contact** — `PUT {{baseUrl}}/contacts/<contact_id>`
```json
{
    "name": "Mother",
    "phone": "+919876543211"
}
```

**4. Delete Contact** — `DELETE {{baseUrl}}/contacts/<contact_id>`

**5. Set Primary Contact** — `PUT {{baseUrl}}/contacts/<contact_id>/primary`

---

### SOS (`/api/sos`)

Requires at least 1 trusted contact, otherwise returns `NO_CONTACTS` error.
Use the **`sos_token`** (not access_token) in the Authorization header for `/sos/trigger`. It's valid for 30 days.

**1. Trigger SOS** — `POST {{baseUrl}}/sos/trigger`

Immediately sends SMS + WhatsApp to all trusted contacts.
```json
{
    "latitude": 28.7041,
    "longitude": 77.1025,
    "trigger_type": "manual"
}
```

**2. Send Now (Dispatch)** — `POST {{baseUrl}}/sos/send-now`
```json
{
    "alert_id": "<alert_id from trigger response>"
}
```

**3. Cancel SOS** — `POST {{baseUrl}}/sos/cancel`
```json
{
    "alert_id": "<alert_id>"
}
```

**4. SOS History** — `GET {{baseUrl}}/sos/history`

---

### Protection (`/api/protection`)

**1. Toggle Protection** — `POST {{baseUrl}}/protection/toggle`
```json
{
    "is_active": true
}
```

**2. Protection Status** — `GET {{baseUrl}}/protection/status`

**3. Send Sensor Data** — `POST {{baseUrl}}/protection/sensor-data`
```json
{
    "sensor_type": "accelerometer",
    "data": [
        {"x": 0.1, "y": 0.2, "z": 1.0, "timestamp": 1700000001},
        {"x": 0.15, "y": 0.18, "z": 0.99, "timestamp": 1700000002}
    ],
    "sensitivity": "medium"
}
```

**4. Predict (Window)** — `POST {{baseUrl}}/protection/predict`

Returns `prediction: 0` (safe) or `1` (danger).
```json
{
    "window": [
        [0.1, 0.2, 1.0],
        [0.15, 0.18, 0.99],
        [0.12, 0.22, 1.01]
    ],
    "location": "Home"
}
```

**5. Collect Training Data** — `POST {{baseUrl}}/protection/collect`
```json
{
    "sensor_type": "accelerometer",
    "data": [
        {"x": 0.1, "y": 0.2, "z": 9.8, "timestamp": 1234567890}
    ],
    "label": 0
}
```

**6. Retrain ML Model** — `POST {{baseUrl}}/protection/train-model`

No auth required. Returns `202` immediately while training runs in background.

---

### Location (`/api/location`)

**1. Update Location** — `POST {{baseUrl}}/location/update`
```json
{
    "latitude": 28.7041,
    "longitude": 77.1025,
    "accuracy": 10.5,
    "is_sharing": false
}
```

**2. Get Current Location** — `GET {{baseUrl}}/location/current`

**3. Start Sharing** — `POST {{baseUrl}}/location/share/start`

**4. Stop Sharing** — `POST {{baseUrl}}/location/share/stop`

---

### Device (`/api/device`)

**1. Register Device** — `POST {{baseUrl}}/device/register`
```json
{
    "device_name": "Asfalis Band v1",
    "device_mac": "AA:BB:CC:DD:EE:FF",
    "firmware_version": "1.0.0"
}
```

**2. Get Device Status** — `GET {{baseUrl}}/device/status`

**3. Update Device Status** — `PUT {{baseUrl}}/device/<device_id>/status`
```json
{
    "is_connected": true
}
```

**4. Device Alert (Bracelet SOS)** — `POST {{baseUrl}}/device/alert`

No JWT required (hardware trigger).
```json
{
    "device_mac": "AA:BB:CC:DD:EE:FF"
}
```

**5. Delete Device** — `DELETE {{baseUrl}}/device/<device_id>`

---

### Settings (`/api/settings`)

**1. Get Settings** — `GET {{baseUrl}}/settings`

**2. Update Settings** — `PUT {{baseUrl}}/settings`
```json
{
    "emergency_number": "+919876543210",
    "shake_sensitivity": "high",
    "battery_optimization": false,
    "haptic_feedback": true
}
```

---

### Support (`/api/support`)

**1. Get FAQs** — `GET {{baseUrl}}/support/faq`

Optional query: `?search=motion`

**2. Create Ticket** — `POST {{baseUrl}}/support/ticket`
```json
{
    "subject": "App keeps crashing on SOS",
    "message": "The app crashes when I try to trigger SOS from the home screen. Using Android 14."
}
```

**3. My Tickets** — `GET {{baseUrl}}/support/tickets`

---

### Health Check

`GET http://localhost:5000/health` — No auth needed.

---

## 4. Testing Flow (Quick Start)

1. **Register** — `POST /auth/register/phone` — copy `data.otp_code` from the response
2. **Verify OTP** — `POST /auth/verify-phone-otp` — tokens auto-saved by the script
3. **Add Contact** — `POST /contacts` — required before SOS; use `invite_message` to notify them
4. **Trigger SOS** — `POST /sos/trigger` — set Auth header to `{{sos_token}}`
5. **Check Profile** — `GET /user/profile`
6. **Test Sensor** — `POST /protection/predict`

---

## 5. Troubleshooting

| Problem | Fix |
|---|---|
| `Missing Authorization Header` | Run **Verify OTP** or **Login** first. Check "Local" env is selected. |
| `PHONE_NOT_VERIFIED` on login | Call `POST /auth/verify-phone-otp` with the OTP from the register response. |
| `NO_CONTACTS` on SOS | Add at least 1 contact first via `POST /contacts`. |
| `Alert already in countdown` | Wait 60 s or cancel via `POST /sos/cancel`. |
| `SOS on cooldown` | Wait 20 s between SOS triggers. |
| `401 Unauthorized` | Token expired — run Login again or call `POST /auth/refresh`. |
| `CONFLICT` on register | Phone already registered — log in instead. |
| `REFRESH_TOKEN_REUSED` | Old refresh token already rotated — log in again. |
"""

import os
target = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "POSTMAN_GUIDE.md")
with open(target, "w") as f:
    f.write(content)
print(f"Written {len(content.splitlines())} lines to {target}")
