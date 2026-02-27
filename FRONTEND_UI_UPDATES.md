# Asfalis — Frontend UI Updates

This document describes every UI and API integration change the frontend/Android team must make following the **email → phone-based auth** migration.

---

## Quick Summary of What Changed

| Area | Old | New |
|------|-----|-----|
| Registration | Email + password | Phone number + password |
| OTP delivery | Server sends email (SendGrid) | **App sends SMS via Android SmsManager** |
| OTP verification | `/auth/verify-email-otp` with `email` | `/auth/verify-phone-otp` with `phone_number` |
| Login | Email + password | Phone number + password |
| Resend OTP | Returns nothing | Returns `otp_code` — app re-sends SMS |
| Forgot password | Email — mocked | Phone number — returns OTP — app sends SMS |
| Trusted contact invite | Server sent email automatically | App sends invite via Android share intent / SMS |
| Login error code | `EMAIL_NOT_VERIFIED` | `PHONE_NOT_VERIFIED` |

---

## 1. Registration Screen

### Fields to Change

| Old field | New field | Type | Validation |
|-----------|-----------|------|------------|
| Email input | **Phone number input** | `tel` / `PhoneEditText` | E.164 format, min 10 digits — e.g. `+919876543210` |
| — | Country dropdown (already existed) | `Spinner` / `DropdownMenu` | Required |
| Password input | Password input | `password` | Min 8 characters — unchanged |
| Full name input | Full name input | `text` | Min 2 characters — unchanged |

> **Remove** the email input field entirely. **Add** a phone number input field with an inline country code picker (or use a library like `libphonenumber` to handle E.164 formatting automatically).

### API Call Change

```
OLD: POST /api/auth/register/email
     Body: { "email", "password", "full_name", "country" }

NEW: POST /api/auth/register/phone
     Body: { "phone_number", "password", "full_name", "country" }
```

### ⚠️ Critical — OTP Handling After Registration

The API now **returns the OTP in the response**. The server does NOT send the SMS. The app must send it:

```json
// Response from POST /api/auth/register/phone
{
    "success": true,
    "data": {
        "phone_number": "+919876543210",
        "otp_code": "482901",
        "expires_in": 300
    }
}
```

**Android implementation:**

```kotlin
// After successful registration response:
val otp = response.data.otp_code
val phoneNumber = response.data.phone_number

val smsManager = SmsManager.getDefault()
smsManager.sendTextMessage(
    phoneNumber,
    null,
    "Your Asfalis verification code is: $otp. Valid for 5 minutes. Do not share.",
    null,
    null
)

// Then navigate to the OTP entry screen
```

> Store `phone_number` locally (in-memory or SharedPreferences) to pre-fill the OTP verification screen.

---

## 2. OTP Verification Screen

### Fields to Change

| Old field | New field |
|-----------|-----------|
| Email input (pre-filled) | Phone number (pre-filled, read-only) |
| 6-digit OTP input | 6-digit OTP input — unchanged |

### API Call Change

```
OLD: POST /api/auth/verify-email-otp
     Body: { "email": "...", "otp_code": "123456" }

NEW: POST /api/auth/verify-phone-otp
     Body: { "phone_number": "+919876543210", "otp_code": "123456" }
```

### Response — Tokens Returned Here

```json
{
    "success": true,
    "data": {
        "user_id": "uuid",
        "full_name": "Test User",
        "phone_number": "+919876543210",
        "access_token": "...",
        "refresh_token": "...",
        "sos_token": "...",
        "expires_in": 900
    }
}
```

**Store all three tokens:**
- `access_token` — use for all standard API calls (expires in 15 min)
- `refresh_token` — use with `POST /auth/refresh` to get new access tokens
- `sos_token` — store securely, use **only** for `POST /sos/trigger` (valid 30 days — ensures SOS always works even if access token expired)

### Resend OTP Button

```
OLD: POST /api/auth/resend-otp
     Body: { "email": "..." }

NEW: POST /api/auth/resend-otp
     Body: { "phone_number": "+919876543210" }
```

Response now returns `otp_code` — the app must re-send the SMS, same as registration:

```json
{
    "success": true,
    "data": {
        "otp_code": "739104",
        "expires_in": 300
    }
}
```

```kotlin
// After resend response:
smsManager.sendTextMessage(
    phoneNumber, null,
    "Your Asfalis verification code is: ${response.data.otp_code}. Valid for 5 minutes. Do not share.",
    null, null
)
```

> Rate-limited to **3 requests per 15 minutes**. Show a countdown timer on the resend button.

---

## 3. Login Screen

### Fields to Change

| Old field | New field | Validation |
|-----------|-----------|------------|
| Email input | **Phone number input** | E.164 format, min 10 digits |
| Password input | Password input | Unchanged |

### API Call Change

```
OLD: POST /api/auth/login/email
     Body: { "email": "...", "password": "..." }

NEW: POST /api/auth/login/phone
     Body: { "phone_number": "+919876543210", "password": "..." }
```

### Error Code Change

| Old error code | New error code | HTTP | UI action |
|----------------|----------------|------|-----------|
| `EMAIL_NOT_VERIFIED` | `PHONE_NOT_VERIFIED` | 403 | Show "Verify your phone number first" — navigate to OTP screen |
| `UNAUTHORIZED` | `UNAUTHORIZED` | 401 | Show "Invalid phone number or password" |

```kotlin
when (error.code) {
    "PHONE_NOT_VERIFIED" -> navigateToOtpScreen(phoneNumber)
    "UNAUTHORIZED" -> showError("Invalid phone number or password")
    "RATE_LIMITED" -> showError("Too many attempts. Try again later.")
}
```

---

## 4. Forgot Password Screen

### Fields to Change

Replace email input with **phone number input**.

### API Call Change

```
OLD: POST /api/auth/forgot-password
     Body: { "email": "..." }

NEW: POST /api/auth/forgot-password
     Body: { "phone_number": "+919876543210" }
```

The response now returns an OTP (same pattern as registration). The app sends the SMS and then navigates to a **reset OTP verification screen** → **new password screen**.

```json
{
    "success": true,
    "data": {
        "otp_code": "201847",
        "expires_in": 300
    }
}
```

> ⚠️ If the phone number is not registered, the API still returns `success: true` with a generic message (security — don't reveal whether a number exists). The `otp_code` key will be absent in that case — check for it before sending the SMS.

---

## 5. Add Trusted Contact Screen

### Field Changes

| Field | Change |
|-------|--------|
| Email input | **Remove** — no longer required or used |
| Name, Phone, Relationship, Is Primary | Unchanged |

### API Call Change

```
OLD: POST /api/contacts
     Body: { "name", "phone", "email", "relationship", "is_primary" }
     Side-effect: server sent notification email to contact

NEW: POST /api/contacts
     Body: { "name", "phone", "relationship", "is_primary" }
     Side-effect: none — app handles the invite
```

### ⚠️ New — Send Invite from the App

After a successful add-contact response, the API returns:

```json
{
    "success": true,
    "data": {
        "id": "uuid",
        "name": "Mom",
        "phone": "+919876543210",
        "whatsapp_join_info": {
            "twilio_number": "+14155238886",
            "sandbox_code": "join something-popular",
            "whatsapp_link": "https://wa.me/14155238886?text=join%20something-popular"
        },
        "invite_message": "Test User added you as a trusted contact in Asfalis..."
    }
}
```

**Show an invite dialog after adding a contact:**

```
┌─────────────────────────────────────┐
│  Notify Mom?                        │
│                                     │
│  Send an invite so they can         │
│  receive WhatsApp alerts.           │
│                                     │
│  [Send SMS]   [Share]   [Skip]      │
└─────────────────────────────────────┘
```

**"Send SMS" button** — compose a pre-filled SMS:

```kotlin
val inviteText = """
${response.data.invite_message}

To receive WhatsApp emergency alerts, save ${response.data.whatsapp_join_info.twilio_number} 
and send: "${response.data.whatsapp_join_info.sandbox_code}"

Or tap: ${response.data.whatsapp_join_info.whatsapp_link}
""".trimIndent()

val intent = Intent(Intent.ACTION_SENDTO).apply {
    data = Uri.parse("smsto:${contact.phone}")
    putExtra("sms_body", inviteText)
}
startActivity(intent)
```

**"Share" button** — use Android share sheet:

```kotlin
val shareIntent = Intent.createChooser(Intent(Intent.ACTION_SEND).apply {
    type = "text/plain"
    putExtra(Intent.EXTRA_TEXT, inviteText)
}, "Invite ${contact.name}")
startActivity(shareIntent)
```

---

## 6. User Profile Screen

### Field Changes

| Old field | New field |
|-----------|-----------|
| Email displayed | **Phone number displayed** |
| Email edit field | Phone number (read-only after verification — changing phone requires re-verification flow) |

The profile API response (`GET /api/user/profile`) returns `phone` instead of `email` as the primary identifier. Update display accordingly.

---

## 7. Token Storage — New `sos_token`

Three tokens are now returned at login/verification. All three must be stored securely (e.g. `EncryptedSharedPreferences`):

| Token | Expiry | Used for |
|-------|--------|----------|
| `access_token` | 15 minutes | All standard API calls |
| `refresh_token` | 30 days | `POST /auth/refresh` to get new access token |
| `sos_token` | 30 days | **Only** `POST /sos/trigger` |

```kotlin
// In your AuthInterceptor / SOS trigger logic:
fun getTokenForRequest(endpoint: String): String {
    return if (endpoint.contains("/sos/trigger")) {
        prefs.getString("sos_token", "")!!
    } else {
        prefs.getString("access_token", "")!!
    }
}
```

> Never refresh the `sos_token` — it is intentionally long-lived. Replace it only on fresh login/verify.

---

## 8. Required Android Permissions

Add to `AndroidManifest.xml` if not already present:

```xml
<!-- For sending OTP via SMS -->
<uses-permission android:name="android.permission.SEND_SMS" />

<!-- For reading own SMS (optional — enables auto-fill OTP from self-sent message) -->
<uses-permission android:name="android.permission.READ_SMS" />
<uses-permission android:name="android.permission.RECEIVE_SMS" />
```

> Request `SEND_SMS` at runtime (it is a dangerous permission) before the registration flow reaches the OTP step.

---

## 9. Error Code Reference

| Code | HTTP | Screen | UI Message |
|------|------|--------|------------|
| `CONFLICT` | 409 | Register | "This phone number is already registered. Try logging in." |
| `PHONE_NOT_VERIFIED` | 403 | Login | "Please verify your phone number first." → navigate to OTP screen |
| `OTP_INVALID` | 422 | OTP Verify | "Incorrect or expired OTP. Try again." |
| `ALREADY_VERIFIED` | 400 | Resend OTP | "Your number is already verified. Please log in." |
| `VALIDATION_ERROR` | 400 | Any | Show field-level errors from `error.details` |
| `UNAUTHORIZED` | 401 | Login | "Invalid phone number or password." |
| `RATE_LIMITED` | 429 | Any | "Too many attempts. Please wait and try again." |
| `TOKEN_EXPIRED` | 401 | Any | Silently refresh token via `POST /auth/refresh` |
| `REFRESH_TOKEN_EXPIRED` | 401 | Any | Force logout → navigate to Login screen |

---

## 10. Screens / Flow Diagram

```
Registration Flow:
─────────────────
Register Screen
  [phone_number, country, full_name, password]
       │
       ▼ POST /auth/register/phone
       │ ← response: { otp_code, phone_number }
       │
  App sends SMS via SmsManager ──────────────────┐
       │                                          │
       ▼                                  User receives SMS
  OTP Screen                              with OTP code
  [pre-filled phone, 6-digit OTP input]
       │
       ▼ POST /auth/verify-phone-otp
       │ ← response: { access_token, refresh_token, sos_token }
       │
  Home Screen ✅

Login Flow:
──────────
Login Screen
  [phone_number, password]
       │
       ▼ POST /auth/login/phone
       │ ← response: { access_token, refresh_token, sos_token }
       │
  Home Screen ✅
       │
  (on PHONE_NOT_VERIFIED 403)
       │
  OTP Screen → re-verify → Home Screen ✅

Add Contact Flow:
─────────────────
Add Contact Screen
  [name, phone, relationship, is_primary]
       │
       ▼ POST /api/contacts
       │ ← response: { ...contact, whatsapp_join_info, invite_message }
       │
  Invite Dialog
  [Send SMS] [Share] [Skip]
       │
  Contact notified ✅
```
