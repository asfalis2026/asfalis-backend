# Security Audit Report - Asfalis Backend

**Date:** 2026-06-06
**Status:** ✅ FIXED - All critical and high issues resolved

---

## Executive Summary

This report documents the security vulnerabilities found in the Asfalis backend and their remediation status. All critical and high-severity issues have been addressed.

---

## Fixed Issues ✅

### 1. Rate Limiting Applied to Auth Endpoints ✅ FIXED

**Original Issue:** Rate limiter was initialized but never applied to any endpoints.

**Fix Applied:**
- Added `@limiter.limit()` decorator to all sensitive auth endpoints:
  - `/api/auth/register/phone` - 5/minute
  - `/api/auth/verify-phone-otp` - 10/minute
  - `/api/auth/resend-otp` - 5/minute
  - `/api/auth/login/phone` - 10/minute
  - `/api/auth/forgot-password` - 5/minute
  - `/api/auth/reset-password` - 10/minute
  - `/api/contacts` (add contact) - 10/minute
  - `/api/contacts/resend-otp` - 5/minute

**Files Modified:** [app/routes/auth.py](app/routes/auth.py), [app/routes/contacts.py](app/routes/contacts.py)

---

### 2. Account Lockout Implementation ✅ FIXED

**Original Issue:** No account lockout after failed login attempts.

**Fix Applied:**
- Added `failed_login_attempts` and `locked_until` columns to User model
- Implemented `is_locked()`, `get_lockout_remaining_seconds()`, `record_failed_login()`, and `reset_failed_logins()` methods
- Login endpoint now:
  - Checks if account is locked before validating credentials
  - Records failed attempts and locks after 5 attempts
  - Returns remaining attempts info in error response
  - Resets failed attempts counter on successful login

**Configuration:**
- `MAX_LOGIN_ATTEMPTS = 5`
- `LOCKOUT_MINUTES = 30`

**Files Modified:** [app/models/user.py](app/models/user.py), [app/routes/auth.py](app/routes/auth.py)

---

### 3. Strong Password Policy ✅ FIXED

**Original Issue:** Weak password validation (only 6 chars + 1 digit).

**Fix Applied:**
- Updated password validation to require:
  - Minimum 8 characters
  - At least 1 uppercase letter
  - At least 1 lowercase letter
  - At least 1 digit
- Updated Pydantic schemas to require minimum 8 characters
- Updated error messages

**Files Modified:** [app/utils/validators.py](app/utils/validators.py), [app/schemas/auth_schema.py](app/schemas/auth_schema.py), [app/routes/auth.py](app/routes/auth.py)

---

### 4. DEBUG OTP Leakage Fixed ✅ FIXED

**Original Issue:** OTP codes returned in responses when `send_result == "mock-sid"`.

**Fix Applied:**
- Changed condition to only return OTP when `settings.DEBUG` is True
- Never returns OTP in production

**Files Modified:** [app/routes/auth.py](app/routes/auth.py)

---

### 5. Unauthenticated Device Endpoints Secured ✅ FIXED

**Original Issue:** `/device/alert` and `/device/cancel-sos` had no authentication.

**Fix Applied:**
- Added JWT authentication (`Depends(get_current_user)`) to both endpoints
- Added verification that device belongs to the authenticated user
- Updated endpoint descriptions

**Files Modified:** [app/routes/device.py](app/routes/device.py)

---

### 6. CORS Configuration Fixed ✅ FIXED

**Original Issue:** Overly permissive CORS (`allow_origins=["*"]`).

**Fix Applied:**
- Changed to use environment variable `ALLOWED_ORIGINS`
- Default allowed origins for development: localhost:3000, localhost:8080
- Restricted allowed methods and headers
- Credentials allowed only with specific origins

**Files Modified:** [app/main.py](app/main.py)

---

### 7. User Deletion Authorization Check ✅ FIXED

**Original Issue:** Any user could delete any other user.

**Fix Applied:**
- Added authorization check ensuring users can only delete their own account
- Returns 403 Forbidden if attempting to delete another user

**Files Modified:** [app/routes/user.py](app/routes/user.py)

---

### 8. Security Headers Added ✅ FIXED

**Original Issue:** No security headers.

**Fix Applied:**
- Added security headers middleware with:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `X-XSS-Protection: 1; mode=block`
  - `Strict-Transport-Security: max-age=31536000; includeSubDomains`
  - `Content-Security-Policy: default-src 'self'`

**Files Modified:** [app/main.py](app/main.py)

---

## Security Best Practices Already Implemented ✅

1. **Password hashing** - bcrypt with proper salt
2. **Field-level encryption** - Fernet for sensitive data
3. **HMAC-based lookups** - Phone numbers stored with deterministic HMAC
4. **JWT token revocation** - Refresh tokens can be revoked
5. **Short-lived access tokens** - 15 minutes
6. **OTP attempt limiting** - 5 attempts per OTP record

---

## Configuration Recommendations

For production deployment, ensure the following environment variables are set:

```bash
# Required
JWT_SECRET_KEY=<strong-random-secret>
FIELD_ENCRYPTION_KEY=<fernet-key>
FIELD_HMAC_KEY=<hmac-secret>

# Security
ALLOWED_ORIGINS=https://asfalis.in,https://asfalis-backend.onrender.com
DEBUG=false

# Optional but recommended
JWT_REFRESH_TOKEN_EXPIRES=604800  # 7 days instead of 30
```

---

## Summary

| Priority | Issue | Status |
|----------|-------|--------|
| P0 | Rate limiting on auth endpoints | ✅ Fixed |
| P0 | Account lockout | ✅ Fixed |
| P1 | Auth on device endpoints | ✅ Fixed |
| P1 | Strong password policy | ✅ Fixed |
| P1 | DEBUG OTP leakage | ✅ Fixed |
| P2 | CORS configuration | ✅ Fixed |
| P2 | User deletion authz | ✅ Fixed |
| P3 | Security headers | ✅ Fixed |

All critical and high-priority security issues have been addressed. The backend is now significantly more secure against common attack vectors including brute force attacks, unauthorized access, and information disclosure.
