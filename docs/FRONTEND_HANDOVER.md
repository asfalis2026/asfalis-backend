# Frontend Handover Document - Security Updates

**Date:** 2026-06-06
**Version:** 2.1.0

---

## Overview

The backend has undergone significant security updates. This document outlines the changes that the Android frontend team needs to be aware of and handle appropriately.

---

## 🔐 Authentication Changes

### 1. Stronger Password Requirements

**What changed:**
- Minimum password length: 6 → **8 characters**
- New requirements: Must contain **uppercase, lowercase, and digit**

**Frontend action:**
- Update password validation in registration/forgot-password flows
- Show appropriate error messages:

```
// New error message example:
"Password must be at least 8 characters with uppercase, lowercase, and digit."
```

---

### 2. Account Lockout Responses

**What changed:**
- After **5 failed login attempts**, account is locked for **30 minutes**
- New HTTP status code: **423 (Locked)**

**Frontend action:**
- Handle 423 status in login response:

```kotlin
// Example Kotlin handling
when (response.code()) {
    423 -> {
        val lockedUntil = response.headers()["locked_until"]
        val secondsRemaining = response.body()?.detail?.get("seconds_remaining")
        // Show: "Account locked. Try again in X minutes."
    }
}
```

**New response format for failed login:**
```json
{
  "detail": {
    "code": "ACCOUNT_LOCKED",
    "message": "Too many failed attempts. Account locked for 30 minutes.",
    "locked_until": "2026-06-06T12:30:00",
    "seconds_remaining": 1800,
    "attempts_remaining": 0
  }
}
```

**Response for failed attempt (before lockout):**
```json
{
  "detail": {
    "code": "INVALID_CREDENTIALS",
    "message": "Invalid phone number or password.",
    "attempts_remaining": 3
  }
}
```

---

### 3. Device Endpoints Now Require Auth

**What changed:**
- `/device/alert` and `/device/cancel-sos` now require authentication
- These endpoints now verify the device belongs to the authenticated user

**Frontend action:**
- No changes needed if using authenticated client
- These endpoints should only be called with valid JWT token

---

## ⚠️ Error Handling Updates

### New Status Codes to Handle

| Status Code | Meaning | Frontend Action |
|-------------|---------|-----------------|
| 423 | Account locked | Show lockout message with timer |
| 429 | Rate limited | Show "Too many requests, slow down" |
| 403 | Forbidden | Check authorization, logout if needed |

### Rate Limited Response (429):
```json
{
  "detail": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests. Please try again later."
  }
}
```

---

## 🔧 Configuration Changes

### CORS Origins

**What changed:**
- Backend now uses `ALLOWED_ORIGINS` environment variable
- Defaults to localhost only in development

**Frontend action:**
- If deploying to production, ensure your domain is added to `ALLOWED_ORIGINS` on the backend
- Contact backend team to whitelist your production domain

---

## 📱 API Response Changes Summary

### Login Response (Success)
```json
{
  "success": true,
  "message": "Login successful.",
  "data": {
    "access_token": "eyJ...",
    "refresh_token": "eyJ...",
    "sos_token": "eyJ...",
    "expires_in": 900,
    "user_id": "uuid",
    "full_name": "John Doe",
    "auth_provider": "phone"
  }
}
```

### Login Response (Locked - 423)
```json
{
  "success": false,
  "error": {
    "code": "ACCOUNT_LOCKED",
    "message": "Too many failed attempts. Account locked for 30 minutes.",
    "locked_until": "2026-06-06T12:30:00",
    "seconds_remaining": 1800,
    "attempts_remaining": 0
  }
}
```

### Registration Error (Weak Password - 400)
```json
{
  "success": false,
  "error": {
    "code": "WEAK_PASSWORD",
    "message": "Password must be at least 8 characters with uppercase, lowercase, and digit."
  }
}
```

---

## 🧪 Testing Checklist

- [ ] Test registration with weak password (should fail with new message)
- [ ] Test login with wrong password 5 times (should get locked)
- [ ] Test rate limiting (make 10+ rapid requests to login)
- [ ] Verify error messages display correctly
- [ ] Test device alert/cancel-sos endpoints with valid auth

---

## 📞 Questions?

If you have any questions about these changes, contact the backend team.

---

## Changelog

| Date | Change |
|------|--------|
| 2026-06-06 | Initial document - Security updates v2.1.0 |
