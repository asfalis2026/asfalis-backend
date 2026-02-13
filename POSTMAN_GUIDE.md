# Raksha Backend - Postman Testing Guide

This guide covers **every API endpoint** in the Raksha backend, with example requests and responses.

## 1. Setup

### Create Environment
1. Open Postman → **Environments** → **Create Environment** ("Local").
2. Add variables:

| Variable | Value |
| :--- | :--- |
| `baseUrl` | `http://localhost:5000/api` |
| `token` | *(leave empty)* |

3. **Save** and select "Local" from the top-right dropdown.

### Collection-Level Auth
1. Create collection **"Raksha Backend"**.
2. Collection → **Authorization** → Type: **Bearer Token** → Token: `{{token}}`.
3. Save. All requests inherit auth automatically.

### Auto-Save Token Script
Add this to the **Tests** tab of the **Login** or **Verify Email OTP** request (NOT the Register request):
```javascript
var jsonData = pm.response.json();
if (jsonData.success && jsonData.data.access_token) {
    pm.environment.set("token", jsonData.data.access_token);
    console.log("Token saved!");
}
```

---

## 2. Endpoints

> **Phone number format:** Always use **E.164** → `+<country_code><number>` (e.g. `+919876543210`). No spaces or dashes.

---

### 📁 Auth (`/api/auth`)

**1. Register (Email)** — `POST {{baseUrl}}/auth/register/email`
> Note: This sends a 6-digit OTP to the email. Tokens are NOT returned here.
```json
{
    "email": "test@example.com",
    "password": "Password123!",
    "full_name": "Test User",
    "country": "India"
}
```

**1a. Verify Email OTP** — `POST {{baseUrl}}/auth/verify-email-otp`
> Returns tokens upon successful verification.
```json
{
    "email": "test@example.com",
    "otp_code": "123456"
}
```

**2. Login (Email)** — `POST {{baseUrl}}/auth/login/email`
```json
{
    "email": "test@example.com",
    "password": "Password123!"
}
```

**3. Google Login** — `POST {{baseUrl}}/auth/google`
```json
{
    "id_token": "google-oauth-id-token-here"
}
```

**4. Send OTP (Phone)** — `POST {{baseUrl}}/auth/send-otp`
```json
{
    "phone": "+919876543210"
}
```

**5. Verify OTP** — `POST {{baseUrl}}/auth/verify-otp`
```json
{
    "phone": "+919876543210",
    "otp_code": "123456"
}
```

**6. Resend OTP** — `POST {{baseUrl}}/auth/resend-otp`
```json
{
    "phone": "+919876543210"
}
```

**7. Forgot Password** — `POST {{baseUrl}}/auth/forgot-password`
```json
{
    "email": "test@example.com"
}
```

**8. Refresh Token** — `POST {{baseUrl}}/auth/refresh`
> Auth: Set Bearer Token to the **refresh_token** (not access_token).

**9. Validate Token** — `GET {{baseUrl}}/auth/validate`
> Returns `is_valid: true` if JWT is valid.

**10. Logout** — `POST {{baseUrl}}/auth/logout`

---

### 📁 User (`/api/user`)

**1. Get Profile** — `GET {{baseUrl}}/user/profile`
> Returns: user info, trusted contacts list, protection status.

**2. Update Profile** — `PUT {{baseUrl}}/user/profile`
```json
{
    "full_name": "Updated Name",
    "phone": "+919876543210"
}
```

**3. Update FCM Token** — `PUT {{baseUrl}}/user/fcm-token`
```json
{
    "fcm_token": "firebase-cloud-messaging-token"
}
```

**4. Delete Account (Self)** — `DELETE {{baseUrl}}/user/account`

**5. Delete User (Admin/Dev)** — `DELETE {{baseUrl}}/user/<user_id>`
> Requires Auth Token. Deletes any user by ID.

---

### 📁 Contacts (`/api/contacts`)

**1. List Contacts** — `GET {{baseUrl}}/contacts`

**2. Add Contact** — `POST {{baseUrl}}/contacts`
```json
{
    "name": "Mom",
    "phone": "+919876543210",
    "email": "mom@example.com",
    "relationship": "Parent",
    "is_primary": true
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

### 📁 SOS (`/api/sos`)

> ⚠ Requires at least 1 trusted contact saved, otherwise returns `NO_CONTACTS` error.

**1. Trigger SOS** — `POST {{baseUrl}}/sos/trigger`
> Immediately sends SMS + WhatsApp to all trusted contacts.
```json
{
    "latitude": 28.7041,
    "longitude": 77.1025,
    "trigger_type": "manual"
}
```

**2. Send Now (Dispatch)** — `POST {{baseUrl}}/sos/send-now`
> Re-dispatch an existing alert.
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

### 📁 Protection (`/api/protection`)

**1. Toggle Protection** — `POST {{baseUrl}}/protection/toggle`
```json
{
    "is_active": true
}
```

**2. Protection Status** — `GET {{baseUrl}}/protection/status`

**3. Send Sensor Data** — `POST {{baseUrl}}/protection/sensor-data`
> Uses ML model to detect danger from individual sensor readings.
```json
{
    "sensor_type": "accelerometer",
    "data": [
        {"x": 0.1, "y": 0.2, "z": 1.0, "timestamp": 1700000001},
        {"x": 0.15, "y": 0.18, "z": 0.99, "timestamp": 1700000002},
        {"x": 0.12, "y": 0.22, "z": 1.01, "timestamp": 1700000003}
    ],
    "sensitivity": "medium"
}
```

**4. Predict (Window)** — `POST {{baseUrl}}/protection/predict`
> Raw sensor window for ML prediction. Returns `prediction: 0` (safe) or `1` (danger).
```json
{
    "window": [
        [0.1, 0.2, 1.0],
        [0.15, 0.18, 0.99],
        [0.12, 0.22, 1.01],
        [0.1, 0.2, 1.0],
        [0.15, 0.18, 0.99]
    ],
    "location": "Home"
}
```

---

### 📁 Location (`/api/location`)

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

### 📁 Device (`/api/device`)

**1. Register Device** — `POST {{baseUrl}}/device/register`
```json
{
    "device_name": "Raksha Band v1",
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
> No JWT required (hardware trigger).
```json
{
    "device_mac": "AA:BB:CC:DD:EE:FF"
}
```

**5. Delete Device** — `DELETE {{baseUrl}}/device/<device_id>`

---

### 📁 Settings (`/api/settings`)

**1. Get Settings** — `GET {{baseUrl}}/settings`

**2. Update Settings** — `PUT {{baseUrl}}/settings`
```json
{
    "emergency_number": "+919876543210",
    "sos_message": "I need help! This is an emergency!",
    "shake_sensitivity": "high",
    "battery_optimization": false,
    "haptic_feedback": true
}
```

---

### 📁 Support (`/api/support`)

**1. Get FAQs** — `GET {{baseUrl}}/support/faq`
> Optional query: `?search=motion`

**2. Create Ticket** — `POST {{baseUrl}}/support/ticket`
```json
{
    "subject": "App keeps crashing on SOS",
    "message": "The app crashes when I try to trigger SOS from the home screen. Using Android 14."
}
```

**3. My Tickets** — `GET {{baseUrl}}/support/tickets`

---

### 🏥 Health Check

**Health** — `GET http://localhost:5000/health`
> No auth needed. Returns `{"status": "healthy", "service": "raksha-backend"}`.

---

## 3. Testing Flow (Quick Start)

1. **Register** → `POST /auth/register/email` (token auto-saved)
2. **Add Contact** → `POST /contacts` (required before SOS)
3. **Trigger SOS** → `POST /sos/trigger` (sends SMS + WhatsApp)
4. **Check Profile** → `GET /user/profile` (see contacts listed)
5. **Test Sensor** → `POST /protection/predict` (ML danger detection)

## 4. Troubleshooting

| Problem | Fix |
|---|---|
| `Missing Authorization Header` | Run Login first. Check "Local" env is selected. Check request Auth is "Inherit from parent". |
| `NO_CONTACTS` on SOS | Add at least 1 contact first via `POST /contacts`. |
| `Alert already in countdown` | Wait 60s (stale alerts auto-expire) or cancel via `POST /sos/cancel`. |
| `SOS on cooldown` | Wait 20s between SOS triggers. |
| `401 Unauthorized` | Token expired. Run Login again or use `POST /auth/refresh`. |
