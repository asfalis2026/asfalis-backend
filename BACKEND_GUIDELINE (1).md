# 🛡️ RAKSHA Women Safety — Backend Guideline (Python Flask)

> **Complete backend specification** for the **RAKSHA Women Safety** Android application.  
> This document maps every frontend feature to its required backend API, database schema, and service logic.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Tech Stack](#2-tech-stack)
3. [Project Structure](#3-project-structure)
4. [Database Schema](#4-database-schema)
5. [Authentication Module](#5-authentication-module)
6. [User Profile Module](#6-user-profile-module)
7. [Trusted Contacts Module](#7-trusted-contacts-module)
8. [SOS Alert Module](#8-sos-alert-module)
9. [Live Location Module](#9-live-location-module)
10. [Protection Monitoring Module](#10-protection-monitoring-module)
11. [Settings Module](#11-settings-module)
12. [Bracelet / IoT Device Module](#12-bracelet--iot-device-module)
13. [Help & Support Module](#13-help--support-module)
14. [Push Notifications (FCM)](#14-push-notifications-fcm)
15. [SMS Gateway Integration](#15-sms-gateway-integration)
16. [API Response Format](#16-api-response-format)
17. [Error Handling](#17-error-handling)
18. [Security Considerations](#18-security-considerations)
19. [Environment Variables](#19-environment-variables)
20. [Deployment Guide](#20-deployment-guide)
21. [Complete API Reference Table](#21-complete-api-reference-table)

---

## 1. Project Overview

**RAKSHA** is a women safety Android application built with Jetpack Compose. The frontend contains the following screens that require backend support:

| Screen | Route | Backend Needed |
|--------|-------|----------------|
| Splash Screen | `app_splash` | ✅ Token validation |
| Onboarding | `onboarding` | ❌ Fully client-side |
| Permissions | `permissions` | ❌ Fully client-side |
| Login | `login` | ✅ Auth gateway |
| Sign In with Email | `sign_in_email` | ✅ Email/password auth |
| Sign In with Phone | `sign_in_phone` | ✅ OTP generation |
| Verify OTP | `verify_otp` | ✅ OTP verification |
| Dashboard | `dashboard` | ✅ Protection status, device status |
| Live Map | `map` | ✅ Location tracking & sharing |
| Trusted Contacts | `contacts` | ✅ CRUD contacts |
| Profile | `profile` | ✅ User data retrieval/update |
| Settings | `settings` | ✅ User preferences |
| SOS Alert | `sos_alert` | ✅ Alert dispatching |
| Help & Support | `help` | ✅ FAQ & support tickets |
| About App | `about` | ❌ Fully client-side |
| Privacy Policy | `privacy_policy` | ❌ Fully client-side |

---

## 2. Tech Stack

| Component | Technology |
|-----------|------------|
| **Framework** | Python Flask |
| **Database** | PostgreSQL (recommended) or MySQL |
| **ORM** | SQLAlchemy + Flask-Migrate |
| **Auth** | JWT (PyJWT / Flask-JWT-Extended) |
| **SMS** | Twilio API |
| **Push Notifications** | Firebase Cloud Messaging (FCM) |
| **Real-time** | Flask-SocketIO (WebSocket for live location) |
| **Task Queue** | Celery + Redis (for async SOS, SMS tasks) |
| **Caching** | Redis |
| **Email** | Flask-Mail / SendGrid |
| **Geocoding** | Google Maps Geocoding API |
| **Deployment** | Docker + Gunicorn + Nginx |

### Python Dependencies (`requirements.txt`)

```txt
Flask==3.1.*
Flask-SQLAlchemy==3.1.*
Flask-Migrate==4.0.*
Flask-JWT-Extended==4.7.*
Flask-SocketIO==5.4.*
Flask-Mail==0.10.*
Flask-CORS==5.0.*
Flask-Limiter==3.8.*
psycopg2-binary==2.9.*
SQLAlchemy==2.0.*
celery==5.4.*
redis==5.2.*
twilio==9.*
firebase-admin==6.*
gunicorn==23.*
python-dotenv==1.0.*
marshmallow==3.23.*
bcrypt==4.2.*
PyJWT==2.10.*
```

---

## 3. Project Structure

```
raksha-backend/
├── app/
│   ├── __init__.py              # Flask app factory
│   ├── config.py                # Configuration classes
│   ├── extensions.py            # DB, JWT, Mail, SocketIO init
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py              # User model
│   │   ├── trusted_contact.py   # Trusted contacts model
│   │   ├── sos_alert.py         # SOS alert logs model
│   │   ├── location.py          # Location history model
│   │   ├── device.py            # Connected IoT device model
│   │   └── settings.py          # User settings model
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── auth.py              # Authentication endpoints
│   │   ├── user.py              # Profile endpoints
│   │   ├── contacts.py          # Trusted contacts CRUD
│   │   ├── sos.py               # SOS alert endpoints
│   │   ├── location.py          # Location sharing endpoints
│   │   ├── settings.py          # Settings endpoints
│   │   ├── device.py            # Bracelet/device endpoints
│   │   └── support.py           # Help & support endpoints
│   ├── services/
│   │   ├── __init__.py
│   │   ├── sms_service.py       # Twilio SMS logic
│   │   ├── fcm_service.py       # Firebase push notifications
│   │   ├── location_service.py  # Geocoding & location logic
│   │   └── sos_service.py       # SOS orchestration
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── auth_schema.py       # Marshmallow schemas
│   │   ├── user_schema.py
│   │   ├── contact_schema.py
│   │   └── settings_schema.py
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── otp.py               # OTP generation/verification
│   │   ├── validators.py        # Input validation helpers
│   │   └── decorators.py        # Custom decorators
│   └── sockets/
│       ├── __init__.py
│       └── location_socket.py   # WebSocket handlers for live location
├── migrations/                  # Flask-Migrate auto-generated
├── celery_worker.py             # Celery entry point
├── wsgi.py                      # WSGI entry point
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── requirements.txt
└── README.md
```

---

## 4. Database Schema

### 4.1 `users` Table

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Unique user ID |
| `full_name` | VARCHAR(100) | NOT NULL | Display name (e.g., "Jessica Parker") |
| `email` | VARCHAR(255) | UNIQUE, NULLABLE | Email address |
| `phone` | VARCHAR(20) | UNIQUE, NULLABLE | Phone number with country code |
| `password_hash` | VARCHAR(255) | NULLABLE | Bcrypt hash (NULL for phone-only auth) |
| `auth_provider` | ENUM | NOT NULL | `email`, `phone`, `google` |
| `profile_image_url` | VARCHAR(500) | NULLABLE | Avatar URL |
| `is_active` | BOOLEAN | DEFAULT TRUE | Account active status |
| `is_verified` | BOOLEAN | DEFAULT FALSE | Email/phone verified |
| `fcm_token` | VARCHAR(500) | NULLABLE | Firebase token for push notifications |
| `created_at` | TIMESTAMP | NOT NULL | Registration date ("Member Since") |
| `updated_at` | TIMESTAMP | NOT NULL | Last update timestamp |

### 4.2 `trusted_contacts` Table

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Unique contact ID |
| `user_id` | UUID | FK → users.id | Owner of the contact |
| `name` | VARCHAR(100) | NOT NULL | Contact name (e.g., "Sarah Johnson") |
| `phone` | VARCHAR(20) | NOT NULL | Contact phone number |
| `email` | VARCHAR(255) | NULLABLE | Contact email |
| `relationship` | VARCHAR(50) | NULLABLE | e.g., "Sister", "Friend" |
| `is_primary` | BOOLEAN | DEFAULT FALSE | Primary emergency contact |
| `created_at` | TIMESTAMP | NOT NULL | Date added |

### 4.3 `sos_alerts` Table

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Alert ID |
| `user_id` | UUID | FK → users.id | Who triggered the alert |
| `trigger_type` | ENUM | NOT NULL | `manual`, `auto_fall`, `auto_shake`, `bracelet` |
| `latitude` | DECIMAL(10,8) | NOT NULL | GPS latitude at trigger time |
| `longitude` | DECIMAL(11,8) | NOT NULL | GPS longitude at trigger time |
| `address` | VARCHAR(500) | NULLABLE | Reverse-geocoded address |
| `status` | ENUM | NOT NULL | `countdown`, `sent`, `cancelled`, `resolved` |
| `sos_message` | TEXT | NOT NULL | The message sent to contacts |
| `contacted_numbers` | JSON | NOT NULL | List of phone numbers notified |
| `triggered_at` | TIMESTAMP | NOT NULL | When countdown started |
| `sent_at` | TIMESTAMP | NULLABLE | When SOS was actually dispatched |
| `resolved_at` | TIMESTAMP | NULLABLE | When user marked safe |

### 4.4 `location_history` Table

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Record ID |
| `user_id` | UUID | FK → users.id | User being tracked |
| `latitude` | DECIMAL(10,8) | NOT NULL | GPS latitude |
| `longitude` | DECIMAL(11,8) | NOT NULL | GPS longitude |
| `address` | VARCHAR(500) | NULLABLE | Reverse-geocoded address |
| `accuracy` | FLOAT | NULLABLE | GPS accuracy in meters |
| `is_sharing` | BOOLEAN | DEFAULT FALSE | Whether actively sharing |
| `recorded_at` | TIMESTAMP | NOT NULL | When location was captured |

### 4.5 `user_settings` Table

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Settings ID |
| `user_id` | UUID | FK → users.id, UNIQUE | One settings row per user |
| `emergency_number` | VARCHAR(20) | NOT NULL | Primary emergency number |
| `sos_message` | TEXT | NOT NULL | Custom SOS message template |
| `shake_sensitivity` | ENUM | DEFAULT 'medium' | `low`, `medium`, `high` |
| `battery_optimization` | BOOLEAN | DEFAULT TRUE | Battery optimization toggle |
| `haptic_feedback` | BOOLEAN | DEFAULT TRUE | Haptic feedback toggle |
| `updated_at` | TIMESTAMP | NOT NULL | Last settings change |

### 4.6 `connected_devices` Table

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Device record ID |
| `user_id` | UUID | FK → users.id | Device owner |
| `device_name` | VARCHAR(100) | NOT NULL | e.g., "Raksha Band v1.0" |
| `device_mac` | VARCHAR(17) | NOT NULL | Bluetooth MAC address |
| `is_connected` | BOOLEAN | DEFAULT FALSE | Current connection status |
| `firmware_version` | VARCHAR(20) | NULLABLE | Firmware version |
| `battery_level` | INTEGER | NULLABLE | Device battery % |
| `last_seen` | TIMESTAMP | NULLABLE | Last communication time |
| `paired_at` | TIMESTAMP | NOT NULL | When first paired |

### 4.7 `otp_records` Table

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Record ID |
| `phone` | VARCHAR(20) | NOT NULL | Phone the OTP was sent to |
| `otp_code` | VARCHAR(6) | NOT NULL | Hashed OTP |
| `purpose` | ENUM | NOT NULL | `login`, `verify`, `reset_password` |
| `attempts` | INTEGER | DEFAULT 0 | Verification attempt count |
| `is_used` | BOOLEAN | DEFAULT FALSE | Whether OTP has been consumed |
| `expires_at` | TIMESTAMP | NOT NULL | OTP expiration time |
| `created_at` | TIMESTAMP | NOT NULL | When OTP was generated |

### 4.8 `support_tickets` Table

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Ticket ID |
| `user_id` | UUID | FK → users.id | Who created the ticket |
| `subject` | VARCHAR(255) | NOT NULL | Ticket subject |
| `message` | TEXT | NOT NULL | Ticket body |
| `status` | ENUM | DEFAULT 'open' | `open`, `in_progress`, `resolved` |
| `created_at` | TIMESTAMP | NOT NULL | When ticket was created |

### ER Diagram (Textual)

```
users (1) ──── (N) trusted_contacts
users (1) ──── (N) sos_alerts
users (1) ──── (N) location_history
users (1) ──── (1) user_settings
users (1) ──── (N) connected_devices
users (1) ──── (N) otp_records
users (1) ──── (N) support_tickets
```

---

## 5. Authentication Module

This module powers: **LoginScreen**, **SignInWithEmail**, **SignInWithPhone**, **VerifyOTPScreen**, **SplashScreen** (token validation), and **ProfileScreen** (logout).

### 5.1 `POST /api/auth/register/email`

**Purpose:** Register a new user with email + password.

**Request Body:**
```json
{
  "full_name": "Jessica Parker",
  "email": "jessica.parker@email.com",
  "password": "SecureP@ss123"
}
```

**Response (201):**
```json
{
  "success": true,
  "data": {
    "user_id": "uuid-here",
    "email": "jessica.parker@email.com",
    "access_token": "eyJhbGci...",
    "refresh_token": "eyJhbGci..."
  },
  "message": "Registration successful"
}
```

**Backend Logic:**
1. Validate email format and password strength (min 8 chars, 1 uppercase, 1 number).
2. Check if email already exists → return 409 Conflict.
3. Hash password with bcrypt (12 rounds).
4. Create user record with `auth_provider = 'email'`.
5. Create default `user_settings` row.
6. Generate JWT access token (15 min expiry) + refresh token (30 days).
7. Return tokens.

---

### 5.2 `POST /api/auth/login/email`

**Purpose:** Sign in with email + password (used by `SignInWithEmail` screen).

**Request Body:**
```json
{
  "email": "jessica.parker@email.com",
  "password": "SecureP@ss123"
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "user_id": "uuid-here",
    "full_name": "Jessica Parker",
    "email": "jessica.parker@email.com",
    "access_token": "eyJhbGci...",
    "refresh_token": "eyJhbGci..."
  }
}
```

**Backend Logic:**
1. Find user by email.
2. Compare bcrypt hash.
3. Return JWT tokens on success.
4. Rate limit: max 5 attempts per 15 minutes per IP.

---

### 5.3 `POST /api/auth/send-otp`

**Purpose:** Send 4-digit OTP to phone number (used by `SignInWithPhone` screen).

**Request Body:**
```json
{
  "phone": "+15550001234"
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "OTP sent successfully",
  "data": {
    "otp_id": "uuid-here",
    "expires_in": 300
  }
}
```

**Backend Logic:**
1. Validate phone number format (E.164).
2. Generate random 4-digit OTP.
3. Hash OTP and store in `otp_records` table with 5 min expiry.
4. Send OTP via Twilio SMS.
5. Rate limit: max 3 OTPs per phone per 15 minutes.

---

### 5.4 `POST /api/auth/verify-otp`

**Purpose:** Verify the 4-digit OTP (used by `VerifyOTPScreen`).

**Request Body:**
```json
{
  "phone": "+15550001234",
  "otp_code": "1234"
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "user_id": "uuid-here",
    "is_new_user": false,
    "access_token": "eyJhbGci...",
    "refresh_token": "eyJhbGci..."
  }
}
```

**Backend Logic:**
1. Find latest non-expired, non-used OTP for the phone number.
2. Compare hashed OTP. Increment `attempts` on failure (max 5).
3. If valid:
   - Mark OTP as used.
   - If user exists with this phone → login (return tokens).
   - If user doesn't exist → create user with `auth_provider = 'phone'`, then return tokens.
4. The `is_new_user` flag tells the frontend if additional profile setup is needed.

---

### 5.5 `POST /api/auth/resend-otp`

**Purpose:** Resend OTP (used by "Resend Code" button in `VerifyOTPScreen`).

**Request Body:**
```json
{
  "phone": "+15550001234"
}
```

**Backend Logic:** Same as `send-otp`, but invalidates any existing unused OTPs for that phone.

---

### 5.6 `POST /api/auth/refresh`

**Purpose:** Refresh an expired access token.

**Request Body:**
```json
{
  "refresh_token": "eyJhbGci..."
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "access_token": "new-eyJhbGci..."
  }
}
```

---

### 5.7 `POST /api/auth/logout`

**Purpose:** Invalidate tokens (used by Sign Out in `ProfileScreen`).

**Headers:** `Authorization: Bearer <access_token>`

**Backend Logic:**
1. Add the token to a Redis blacklist (with TTL matching token expiry).
2. Clear the user's `fcm_token`.

---

### 5.8 `GET /api/auth/validate`

**Purpose:** Validate token on app launch (`SplashScreen` checks `is_logged_in`).

**Headers:** `Authorization: Bearer <access_token>`

**Response (200):**
```json
{
  "success": true,
  "data": {
    "user_id": "uuid-here",
    "is_valid": true
  }
}
```

---

### 5.9 `POST /api/auth/forgot-password`

**Purpose:** Initiate password reset (used by "Forgot password?" in `SignInWithEmail`).

**Request Body:**
```json
{
  "email": "jessica.parker@email.com"
}
```

**Backend Logic:**
1. Generate a password reset token (UUID, 15 min expiry).
2. Send reset link via email (or OTP via SMS if phone auth).

---

### 5.10 `POST /api/auth/google`

**Purpose:** Google Sign-In (placeholder in `LoginScreen`).

**Request Body:**
```json
{
  "id_token": "google-id-token-here"
}
```

**Backend Logic:**
1. Verify Google ID token using Google's API.
2. Extract email and profile info.
3. Find or create user with `auth_provider = 'google'`.
4. Return JWT tokens.

---

## 6. User Profile Module

Powers: **ProfileScreen** (display user info, personal information, system status).

### 6.1 `GET /api/user/profile`

**Headers:** `Authorization: Bearer <access_token>`

**Response (200):**
```json
{
  "success": true,
  "data": {
    "user_id": "uuid-here",
    "full_name": "Jessica Parker",
    "email": "jessica.parker@email.com",
    "phone": "+1 (555) 123-4567",
    "profile_image_url": null,
    "emergency_contact": "+1 (911) 000-0000",
    "member_since": "January 2026",
    "is_protection_active": true,
    "auth_provider": "email"
  }
}
```

### 6.2 `PUT /api/user/profile`

**Headers:** `Authorization: Bearer <access_token>`

**Request Body:**
```json
{
  "full_name": "Jessica M. Parker",
  "phone": "+15551234567",
  "profile_image_url": "https://..."
}
```

### 6.3 `PUT /api/user/fcm-token`

**Purpose:** Register/update the FCM token for push notifications.

**Request Body:**
```json
{
  "fcm_token": "fcm-token-string"
}
```

### 6.4 `DELETE /api/user/account`

**Purpose:** Delete user account and all associated data.

---

## 7. Trusted Contacts Module

Powers: **TrustedContactsScreen** (CRUD operations on emergency contacts). The `LiveMapScreen` shows "Sharing with 2 contacts — Sarah Johnson, Michael Chen".

### 7.1 `GET /api/contacts`

**Headers:** `Authorization: Bearer <access_token>`

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "id": "uuid-1",
      "name": "Sarah Johnson",
      "phone": "+15550001111",
      "email": "sarah@email.com",
      "relationship": "Sister",
      "is_primary": true
    },
    {
      "id": "uuid-2",
      "name": "Michael Chen",
      "phone": "+15550002222",
      "email": null,
      "relationship": "Friend",
      "is_primary": false
    }
  ],
  "count": 2
}
```

### 7.2 `POST /api/contacts`

**Request Body:**
```json
{
  "name": "Sarah Johnson",
  "phone": "+15550001111",
  "email": "sarah@email.com",
  "relationship": "Sister",
  "is_primary": true
}
```

**Backend Logic:**
1. Validate phone format.
2. Enforce max 5 trusted contacts per user.
3. If `is_primary = true`, unset any existing primary contact.
4. Return the created contact.

### 7.3 `PUT /api/contacts/<contact_id>`

Update a specific trusted contact.

### 7.4 `DELETE /api/contacts/<contact_id>`

Delete a trusted contact. Cannot delete if it's the only primary contact.

### 7.5 `PUT /api/contacts/<contact_id>/primary`

Set a contact as the primary emergency contact.

---

## 8. SOS Alert Module

Powers: **SOSAlertScreen** (10-second countdown, "I'M SAFE" button, "SEND SOS NOW" button). Also powers the automatic SOS triggered by motion detection from `DashboardScreen` ("System Active • Monitoring Movement").

### 8.1 `POST /api/sos/trigger`

**Purpose:** Start an SOS alert (countdown initiated by frontend).

**Headers:** `Authorization: Bearer <access_token>`

**Request Body:**
```json
{
  "trigger_type": "manual",
  "latitude": 40.7128,
  "longitude": -74.0060,
  "accuracy": 10.5
}
```

**Response (201):**
```json
{
  "success": true,
  "data": {
    "alert_id": "uuid-here",
    "status": "countdown",
    "countdown_seconds": 10,
    "contacts_to_notify": 2
  }
}
```

**Backend Logic:**
1. Create `sos_alerts` record with status `countdown`.
2. Reverse-geocode the coordinates to get a human-readable address.
3. Start a Celery delayed task (10 seconds) that will dispatch the alert if not cancelled.
4. Return alert ID so frontend can cancel if user presses "I'M SAFE".

---

### 8.2 `POST /api/sos/send-now`

**Purpose:** Immediately dispatch SOS without waiting for countdown (used by "SEND SOS NOW" button).

**Request Body:**
```json
{
  "alert_id": "uuid-here"
}
```

**Backend Logic:**
1. Cancel any pending countdown task.
2. Update alert status to `sent`.
3. Execute the SOS dispatch pipeline immediately (see 8.5).

---

### 8.3 `POST /api/sos/cancel`

**Purpose:** Cancel the SOS during countdown (used by "I'M SAFE" button).

**Request Body:**
```json
{
  "alert_id": "uuid-here"
}
```

**Backend Logic:**
1. Cancel the Celery delayed task.
2. Update alert status to `cancelled`.
3. Update `resolved_at` timestamp.

---

### 8.4 `GET /api/sos/history`

**Purpose:** Get user's SOS alert history.

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "alert_id": "uuid",
      "trigger_type": "auto_fall",
      "address": "123 Safety Street, Downtown",
      "status": "resolved",
      "triggered_at": "2026-02-09T14:30:00Z",
      "resolved_at": "2026-02-09T14:30:08Z"
    }
  ]
}
```

---

### 8.5 SOS Dispatch Pipeline (Internal Service)

When an SOS is dispatched (either after countdown or immediately), the `sos_service.py` must:

1. **Fetch all trusted contacts** for the user.
2. **Compose the SOS message** using the user's custom template from `user_settings.sos_message`:
   ```
   "Emergency! I need help. This is an automated SOS alert from Women Safety app.
   My live location is attached.
   📍 Location: 123 Safety Street, Downtown District
   🗺️ Maps: https://maps.google.com/?q=40.7128,-74.0060
   — Sent by RAKSHA for Jessica Parker"
   ```
3. **Send SMS** to all trusted contacts via Twilio.
4. **Send push notifications** via FCM to any trusted contacts who also use the app.
5. **Start location sharing** automatically (update `is_sharing = true`).
6. **Log all contacted numbers** in the alert record.
7. **Update alert status** to `sent` with `sent_at` timestamp.

---

## 9. Live Location Module

Powers: **LiveMapScreen** (current location display, "Share Live Location" / "Stop Sharing", location sharing with contacts, GPS badge).

### 9.1 `POST /api/location/update`

**Purpose:** Update user's current location (called periodically by frontend).

**Request Body:**
```json
{
  "latitude": 40.7128,
  "longitude": -74.0060,
  "accuracy": 10.5,
  "is_sharing": true
}
```

**Backend Logic:**
1. Store in `location_history`.
2. If `is_sharing = true`, broadcast via WebSocket to all connected trusted contacts.
3. Reverse-geocode if address field is stale.

---

### 9.2 `GET /api/location/current`

**Purpose:** Get user's last known location.

**Response:**
```json
{
  "success": true,
  "data": {
    "latitude": 40.7128,
    "longitude": -74.0060,
    "address": "123 Safety Street, Downtown District",
    "accuracy": "High",
    "is_sharing": false,
    "recorded_at": "2026-02-09T14:30:00Z"
  }
}
```

---

### 9.3 `POST /api/location/share/start`

**Purpose:** Start sharing live location with trusted contacts.

**Backend Logic:**
1. Set `is_sharing = true` in the latest location record.
2. Send notifications to all trusted contacts: "Jessica is now sharing her live location."
3. Generate a shareable tracking URL for non-app users.
4. Return the list of contacts being shared with.

**Response:**
```json
{
  "success": true,
  "data": {
    "sharing_session_id": "uuid-here",
    "shared_with": [
      { "name": "Sarah Johnson", "phone": "+15550001111" },
      { "name": "Michael Chen", "phone": "+15550002222" }
    ],
    "tracking_url": "https://raksha.app/track/abc123"
  }
}
```

---

### 9.4 `POST /api/location/share/stop`

**Purpose:** Stop sharing live location.

**Backend Logic:**
1. Set `is_sharing = false`.
2. Notify contacts that sharing has ended.
3. Close WebSocket channels.

---

### 9.5 WebSocket: Live Location Streaming

**Namespace:** `/location`

**Events:**

| Event | Direction | Payload | Description |
|-------|-----------|---------|-------------|
| `connect` | Client → Server | `{ token: "jwt" }` | Authenticate WebSocket |
| `location_update` | Client → Server | `{ lat, lng, accuracy }` | Real-time location push |
| `location_broadcast` | Server → Client | `{ user_id, lat, lng, address }` | Sent to trusted contacts |
| `sharing_started` | Server → Client | `{ user_name, tracking_url }` | Notify contacts |
| `sharing_stopped` | Server → Client | `{ user_name }` | Notify contacts |

---

## 10. Protection Monitoring Module

Powers: **DashboardScreen** (Protection ON/OFF toggle, "System Active • Monitoring Movement" status bar).

### 10.1 `POST /api/protection/toggle`

**Request Body:**
```json
{
  "is_active": true
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "is_active": true,
    "activated_at": "2026-02-09T14:30:00Z",
    "message": "Protection monitoring is now active"
  }
}
```

**Backend Logic:**
1. Update user's protection status.
2. If turning ON: start expecting periodic sensor data from the device.
3. If turning OFF: stop monitoring, close any active monitoring sessions.

---

### 10.2 `POST /api/protection/sensor-data`

**Purpose:** Receive accelerometer/gyroscope data for fall/impact detection (server-side analysis).

**Request Body:**
```json
{
  "sensor_type": "accelerometer",
  "data": [
    { "x": 0.1, "y": 9.8, "z": 0.2, "timestamp": 1707487800 },
    { "x": 15.5, "y": -3.2, "z": 8.1, "timestamp": 1707487801 }
  ],
  "sensitivity": "medium"
}
```

**Backend Logic:**
1. Analyze acceleration magnitude: `√(x² + y² + z²)`.
2. Apply sensitivity thresholds:
   - **Low:** > 30 m/s² triggers alert
   - **Medium:** > 20 m/s² triggers alert
   - **High:** > 12 m/s² triggers alert
3. If threshold exceeded → trigger SOS via `POST /api/sos/trigger` with `trigger_type = 'auto_fall'`.
4. Send FCM notification to the user's device to show the SOS countdown screen.

---

### 10.3 `GET /api/protection/status`

**Response:**
```json
{
  "success": true,
  "data": {
    "is_active": true,
    "activated_at": "2026-02-09T14:30:00Z",
    "monitoring_duration_minutes": 45,
    "last_sensor_data_at": "2026-02-09T15:14:00Z",
    "bracelet_connected": true
  }
}
```

---

## 11. Settings Module

Powers: **SettingsScreen** (Emergency Contact, SOS Message, Shake Sensitivity, Battery Optimization, Haptic Feedback).

### 11.1 `GET /api/settings`

**Headers:** `Authorization: Bearer <access_token>`

**Response (200):**
```json
{
  "success": true,
  "data": {
    "emergency_number": "+1 (911) 000-0000",
    "sos_message": "Emergency! I need help. This is an automated SOS alert from Women Safety app. My live location is attached.",
    "shake_sensitivity": "medium",
    "battery_optimization": true,
    "haptic_feedback": true
  }
}
```

### 11.2 `PUT /api/settings`

**Request Body (partial update supported):**
```json
{
  "emergency_number": "+19110000001",
  "sos_message": "Help! I'm in danger. Please check my location.",
  "shake_sensitivity": "high",
  "battery_optimization": false,
  "haptic_feedback": true
}
```

**Backend Logic:**
1. Validate `shake_sensitivity` is one of `low`, `medium`, `high`.
2. Validate phone number format for `emergency_number`.
3. Update the `user_settings` row.
4. If `shake_sensitivity` changed, update the active protection monitoring threshold.

---

## 12. Bracelet / IoT Device Module

Powers: **DashboardScreen** (Connected Device section, SearchDeviceContent bottom sheet, Bluetooth scanning UI).

### 12.1 `POST /api/device/register`

**Purpose:** Register a Raksha Band after BLE pairing.

**Request Body:**
```json
{
  "device_name": "Raksha Band v1.0",
  "device_mac": "AA:BB:CC:DD:EE:FF",
  "firmware_version": "1.0.0"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "device_id": "uuid-here",
    "device_name": "Raksha Band v1.0",
    "is_connected": true,
    "paired_at": "2026-02-09T14:30:00Z"
  }
}
```

### 12.2 `GET /api/device/status`

**Purpose:** Get connected device status (powers the "Bracelet Connected" / "Bracelet not connected" UI).

**Response:**
```json
{
  "success": true,
  "data": {
    "device_id": "uuid-here",
    "device_name": "Raksha Band v1.0",
    "is_connected": true,
    "battery_level": 85,
    "firmware_version": "1.0.0",
    "signal_strength": "strong",
    "last_seen": "2026-02-09T15:10:00Z"
  }
}
```

### 12.3 `PUT /api/device/<device_id>/status`

**Purpose:** Update connection status (connect/disconnect from bottom sheet).

**Request Body:**
```json
{
  "is_connected": false
}
```

### 12.4 `POST /api/device/alert`

**Purpose:** Receive SOS trigger from the Raksha Band hardware.

**Request Body:**
```json
{
  "device_mac": "AA:BB:CC:DD:EE:FF",
  "alert_type": "button_press",
  "battery_level": 72
}
```

**Backend Logic:**
1. Identify user by device MAC.
2. Get user's latest location.
3. Trigger SOS pipeline with `trigger_type = 'bracelet'`.

### 12.5 `DELETE /api/device/<device_id>`

**Purpose:** Unpair and remove a device.

---

## 13. Help & Support Module

Powers: **HelpSupportScreen** (FAQ list, search, "Contact Support" button).

### 13.1 `GET /api/support/faq`

**Query Params:** `?search=motion+detection`

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "question": "How does motion detection work?",
      "answer": "Our app uses your device's accelerometer to detect unusual movements...",
      "category": "features",
      "icon": "timeline"
    },
    {
      "id": 2,
      "question": "When is SOS triggered automatically?",
      "answer": "SOS is triggered on sudden impacts, falls, or vigorous shaking...",
      "category": "sos",
      "icon": "flash_on"
    }
  ]
}
```

### 13.2 `POST /api/support/ticket`

**Purpose:** Create a support ticket (used by "Contact Support" button).

**Request Body:**
```json
{
  "subject": "Cannot connect bracelet",
  "message": "I've been trying to pair my Raksha Band but it won't connect..."
}
```

**Response (201):**
```json
{
  "success": true,
  "data": {
    "ticket_id": "uuid-here",
    "status": "open",
    "created_at": "2026-02-09T14:30:00Z"
  },
  "message": "Support ticket created. We'll respond within 24 hours."
}
```

### 13.3 `GET /api/support/tickets`

**Purpose:** List user's support tickets.

---

## 14. Push Notifications (FCM)

### Integration Setup

```python
# app/services/fcm_service.py

import firebase_admin
from firebase_admin import credentials, messaging

cred = credentials.Certificate("path/to/serviceAccountKey.json")
firebase_admin.initialize_app(cred)

def send_push_notification(fcm_token: str, title: str, body: str, data: dict = None):
    message = messaging.Message(
        notification=messaging.Notification(title=title, body=body),
        data=data or {},
        token=fcm_token,
        android=messaging.AndroidConfig(
            priority="high",
            notification=messaging.AndroidNotification(
                channel_id="sos_channel",
                sound="alarm",
                priority="max"
            )
        )
    )
    return messaging.send(message)

def send_sos_notification(user_name: str, location: str, contact_tokens: list):
    """Notify trusted contacts about an SOS alert."""
    for token in contact_tokens:
        send_push_notification(
            fcm_token=token,
            title="🚨 EMERGENCY ALERT",
            body=f"{user_name} has triggered an SOS alert! Location: {location}",
            data={
                "type": "sos_alert",
                "action": "open_tracking"
            }
        )
```

### Notification Scenarios

| Trigger | Recipient | Title | Body |
|---------|-----------|-------|------|
| SOS triggered | Trusted contacts | 🚨 EMERGENCY ALERT | "{name} has triggered an SOS!" |
| Auto-fall detected | User's device | ⚠️ Fall Detected | "Unusual movement detected. SOS countdown started." |
| Location sharing started | Trusted contacts | 📍 Location Shared | "{name} is sharing live location with you" |
| Location sharing stopped | Trusted contacts | 📍 Sharing Ended | "{name} has stopped sharing location" |
| Bracelet disconnected | User's device | ⌚ Device Disconnected | "Your Raksha Band has disconnected" |
| Support ticket reply | User | 💬 Support Reply | "Your ticket has been updated" |

---

## 15. SMS Gateway Integration

### Twilio Integration

```python
# app/services/sms_service.py

from twilio.rest import Client
from app.config import Config

client = Client(Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN)

def send_sms(to: str, body: str):
    """Send an SMS message via Twilio."""
    message = client.messages.create(
        body=body,
        from_=Config.TWILIO_PHONE_NUMBER,
        to=to
    )
    return message.sid

def send_otp_sms(phone: str, otp_code: str):
    """Send OTP for phone authentication."""
    body = f"Your RAKSHA verification code is: {otp_code}. Valid for 5 minutes. Do not share."
    return send_sms(phone, body)

def send_sos_sms(contact_phone: str, user_name: str, message: str, location_url: str):
    """Send SOS alert SMS to a trusted contact."""
    body = (
        f"🚨 RAKSHA EMERGENCY ALERT 🚨\n\n"
        f"{message}\n\n"
        f"Sent by: {user_name}\n"
        f"📍 Live Location: {location_url}\n\n"
        f"This is an automated alert from the RAKSHA Women Safety app."
    )
    return send_sms(contact_phone, body)
```

### SMS Use Cases

| Use Case | Frontend Trigger | SMS Content |
|----------|-----------------|-------------|
| OTP verification | `SignInWithPhone` → "Send OTP" | "Your RAKSHA verification code is: 1234" |
| SOS alert | `SOSAlertScreen` → countdown expires or "SEND SOS NOW" | Emergency message + live location link |
| Password reset | `SignInWithEmail` → "Forgot password?" | "Reset your password: link" |

---

## 16. API Response Format

All API responses must follow this consistent format:

### Success Response

```json
{
  "success": true,
  "data": { ... },
  "message": "Optional success message",
  "meta": {
    "page": 1,
    "per_page": 20,
    "total": 45
  }
}
```

### Error Response

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Email address is invalid",
    "details": {
      "field": "email",
      "reason": "Invalid format"
    }
  }
}
```

---

## 17. Error Handling

### Error Code Reference

| HTTP Status | Error Code | Description | Used By |
|-------------|-----------|-------------|---------|
| 400 | `VALIDATION_ERROR` | Invalid request body | All endpoints |
| 401 | `UNAUTHORIZED` | Missing or invalid JWT | All protected endpoints |
| 401 | `TOKEN_EXPIRED` | JWT has expired | All protected endpoints |
| 403 | `FORBIDDEN` | User lacks permission | Admin endpoints |
| 404 | `NOT_FOUND` | Resource doesn't exist | GET/PUT/DELETE endpoints |
| 409 | `CONFLICT` | Duplicate resource | Registration |
| 422 | `OTP_EXPIRED` | OTP has expired | `verify-otp` |
| 422 | `OTP_INVALID` | OTP code is wrong | `verify-otp` |
| 422 | `MAX_ATTEMPTS` | Too many OTP attempts | `verify-otp` |
| 429 | `RATE_LIMITED` | Too many requests | OTP, login endpoints |
| 500 | `INTERNAL_ERROR` | Server error | All endpoints |
| 503 | `SMS_FAILED` | Twilio SMS delivery failed | OTP, SOS |

### Global Error Handler

```python
# app/__init__.py

@app.errorhandler(400)
def bad_request(e):
    return jsonify(success=False, error={"code": "VALIDATION_ERROR", "message": str(e)}), 400

@app.errorhandler(401)
def unauthorized(e):
    return jsonify(success=False, error={"code": "UNAUTHORIZED", "message": "Authentication required"}), 401

@app.errorhandler(404)
def not_found(e):
    return jsonify(success=False, error={"code": "NOT_FOUND", "message": "Resource not found"}), 404

@app.errorhandler(429)
def rate_limited(e):
    return jsonify(success=False, error={"code": "RATE_LIMITED", "message": "Too many requests. Try again later."}), 429

@app.errorhandler(500)
def internal_error(e):
    return jsonify(success=False, error={"code": "INTERNAL_ERROR", "message": "An unexpected error occurred"}), 500
```

---

## 18. Security Considerations

### 18.1 Authentication & Authorization

- **JWT tokens** with short-lived access tokens (15 min) and long-lived refresh tokens (30 days).
- **Token blacklisting** via Redis for logout.
- **bcrypt** password hashing with 12 rounds.
- All protected endpoints require `Authorization: Bearer <token>` header.

### 18.2 Rate Limiting

```python
from flask_limiter import Limiter

limiter = Limiter(key_func=get_remote_address)

# Apply to sensitive routes
@auth_bp.route('/login/email', methods=['POST'])
@limiter.limit("5/15minutes")
def login_email(): ...

@auth_bp.route('/send-otp', methods=['POST'])
@limiter.limit("3/15minutes")
def send_otp(): ...
```

### 18.3 Data Protection

- **HTTPS only** — all traffic must be encrypted.
- **Location data encryption** — encrypt latitude/longitude at rest.
- **End-to-end encryption** — location data shared with contacts should be encrypted in transit.
- **Data retention policy** — auto-delete location history older than 30 days.
- **CORS** — restrict to the app's domain/origins only.

### 18.4 Input Validation

- Validate all phone numbers using E.164 format.
- Sanitize all text inputs (SOS messages, names) to prevent injection.
- Validate GPS coordinates: latitude (-90 to 90), longitude (-180 to 180).
- Limit request body sizes (max 1MB).

### 18.5 Privacy (As per PrivacyPolicyScreen)

The Privacy Policy screen states the app collects:
- **Location Data**: Real-time GPS coordinates → stored encrypted
- **Device Information**: Motion sensor data, device model, OS version
- **Contact Information**: Emergency contacts provided by user
- **Account Data**: Name, email, phone number

Ensure compliance with these promises in the backend:
- Only share location with designated emergency contacts when alerts trigger.
- Implement data export (`GET /api/user/data-export`).
- Implement account deletion (`DELETE /api/user/account`) that removes ALL user data.

---

## 19. Environment Variables

```env
# .env.example

# Flask
FLASK_APP=wsgi.py
FLASK_ENV=production
SECRET_KEY=your-secret-key-change-this

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/raksha_db

# JWT
JWT_SECRET_KEY=your-jwt-secret-key
JWT_ACCESS_TOKEN_EXPIRES=900        # 15 minutes in seconds
JWT_REFRESH_TOKEN_EXPIRES=2592000   # 30 days in seconds

# Twilio (SMS)
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+15551234567

# Firebase (Push Notifications)
FIREBASE_CREDENTIALS_PATH=./firebase-service-account.json

# Redis
REDIS_URL=redis://localhost:6379/0

# Google Maps (Geocoding)
GOOGLE_MAPS_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXX

# Email (Flask-Mail)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=raksha.noreply@gmail.com
MAIL_PASSWORD=app-specific-password

# App Settings
OTP_EXPIRY_SECONDS=300
MAX_TRUSTED_CONTACTS=5
MAX_OTP_ATTEMPTS=5
LOCATION_HISTORY_RETENTION_DAYS=30
```

---

## 20. Deployment Guide

### Docker Setup

```dockerfile
# Dockerfile

FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["gunicorn", "--worker-class", "eventlet", "-w", "4", "-b", "0.0.0.0:5000", "wsgi:app"]
```

```yaml
# docker-compose.yml

version: "3.9"

services:
  web:
    build: .
    ports:
      - "5000:5000"
    env_file: .env
    depends_on:
      - db
      - redis
    restart: unless-stopped

  celery_worker:
    build: .
    command: celery -A celery_worker.celery worker --loglevel=info
    env_file: .env
    depends_on:
      - db
      - redis
    restart: unless-stopped

  celery_beat:
    build: .
    command: celery -A celery_worker.celery beat --loglevel=info
    env_file: .env
    depends_on:
      - redis
    restart: unless-stopped

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: raksha_db
      POSTGRES_USER: raksha_user
      POSTGRES_PASSWORD: secure_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    restart: unless-stopped

volumes:
  postgres_data:
```

### Running Locally

```bash
# 1. Clone and set up
git clone <repo-url>
cd raksha-backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your actual values

# 3. Initialize database
flask db init
flask db migrate -m "Initial migration"
flask db upgrade

# 4. Seed FAQ data
flask seed-faqs

# 5. Start Redis (required for Celery & token blacklisting)
redis-server &

# 6. Start Celery worker (for async SOS dispatching)
celery -A celery_worker.celery worker --loglevel=info &

# 7. Run Flask app
flask run --host=0.0.0.0 --port=5000
```

---

## 21. Complete API Reference Table

| # | Method | Endpoint | Auth | Module | Frontend Screen |
|---|--------|----------|------|--------|----------------|
| 1 | POST | `/api/auth/register/email` | ❌ | Auth | SignInWithEmail |
| 2 | POST | `/api/auth/login/email` | ❌ | Auth | SignInWithEmail |
| 3 | POST | `/api/auth/send-otp` | ❌ | Auth | SignInWithPhone |
| 4 | POST | `/api/auth/verify-otp` | ❌ | Auth | VerifyOTPScreen |
| 5 | POST | `/api/auth/resend-otp` | ❌ | Auth | VerifyOTPScreen |
| 6 | POST | `/api/auth/refresh` | 🔄 Refresh | Auth | App-wide |
| 7 | POST | `/api/auth/logout` | ✅ | Auth | ProfileScreen |
| 8 | GET | `/api/auth/validate` | ✅ | Auth | SplashScreen |
| 9 | POST | `/api/auth/forgot-password` | ❌ | Auth | SignInWithEmail |
| 10 | POST | `/api/auth/google` | ❌ | Auth | LoginScreen |
| 11 | GET | `/api/user/profile` | ✅ | Profile | ProfileScreen |
| 12 | PUT | `/api/user/profile` | ✅ | Profile | ProfileScreen |
| 13 | PUT | `/api/user/fcm-token` | ✅ | Profile | App launch |
| 14 | DELETE | `/api/user/account` | ✅ | Profile | Settings |
| 15 | GET | `/api/contacts` | ✅ | Contacts | TrustedContactsScreen |
| 16 | POST | `/api/contacts` | ✅ | Contacts | TrustedContactsScreen |
| 17 | PUT | `/api/contacts/<id>` | ✅ | Contacts | TrustedContactsScreen |
| 18 | DELETE | `/api/contacts/<id>` | ✅ | Contacts | TrustedContactsScreen |
| 19 | PUT | `/api/contacts/<id>/primary` | ✅ | Contacts | TrustedContactsScreen |
| 20 | POST | `/api/sos/trigger` | ✅ | SOS | SOSAlertScreen |
| 21 | POST | `/api/sos/send-now` | ✅ | SOS | SOSAlertScreen |
| 22 | POST | `/api/sos/cancel` | ✅ | SOS | SOSAlertScreen |
| 23 | GET | `/api/sos/history` | ✅ | SOS | Profile / History |
| 24 | POST | `/api/location/update` | ✅ | Location | LiveMapScreen |
| 25 | GET | `/api/location/current` | ✅ | Location | LiveMapScreen |
| 26 | POST | `/api/location/share/start` | ✅ | Location | LiveMapScreen |
| 27 | POST | `/api/location/share/stop` | ✅ | Location | LiveMapScreen |
| 28 | POST | `/api/protection/toggle` | ✅ | Protection | DashboardScreen |
| 29 | POST | `/api/protection/sensor-data` | ✅ | Protection | DashboardScreen |
| 30 | GET | `/api/protection/status` | ✅ | Protection | DashboardScreen |
| 31 | GET | `/api/settings` | ✅ | Settings | SettingsScreen |
| 32 | PUT | `/api/settings` | ✅ | Settings | SettingsScreen |
| 33 | POST | `/api/device/register` | ✅ | Device | DashboardScreen |
| 34 | GET | `/api/device/status` | ✅ | Device | DashboardScreen |
| 35 | PUT | `/api/device/<id>/status` | ✅ | Device | DashboardScreen |
| 36 | POST | `/api/device/alert` | 🔑 API Key | Device | Raksha Band HW |
| 37 | DELETE | `/api/device/<id>` | ✅ | Device | DashboardScreen |
| 38 | GET | `/api/support/faq` | ✅ | Support | HelpSupportScreen |
| 39 | POST | `/api/support/ticket` | ✅ | Support | HelpSupportScreen |
| 40 | GET | `/api/support/tickets` | ✅ | Support | HelpSupportScreen |

### WebSocket Endpoints

| Namespace | Event | Direction | Description |
|-----------|-------|-----------|-------------|
| `/location` | `connect` | Client → Server | Auth with JWT |
| `/location` | `location_update` | Client → Server | Push location data |
| `/location` | `location_broadcast` | Server → Client | Broadcast to contacts |
| `/location` | `sharing_started` | Server → Client | Notify sharing began |
| `/location` | `sharing_stopped` | Server → Client | Notify sharing ended |

---

## Frontend Integration Notes

### SharedPreferences Mapping → Backend

The frontend currently uses `SharedPreferences` (`raksha_prefs`) for local state. With the backend, these should be mapped:

| SharedPref Key | Backend Replacement |
|----------------|-------------------|
| `onboarding_complete` | Keep client-side (no backend needed) |
| `is_logged_in` | Replace with JWT token existence check + `GET /api/auth/validate` |

### Hardcoded Data → Backend Dynamic Data

The frontend currently has hardcoded data that should come from the backend:

| Screen | Hardcoded Value | Backend Source |
|--------|----------------|---------------|
| ProfileScreen | "Jessica Parker" | `GET /api/user/profile` → `full_name` |
| ProfileScreen | "jessica.parker@email.com" | `GET /api/user/profile` → `email` |
| ProfileScreen | "+1 (555) 123-4567" | `GET /api/user/profile` → `phone` |
| ProfileScreen | "+1 (911) 000-0000" | `GET /api/user/profile` → `emergency_contact` |
| ProfileScreen | "January 2026" | `GET /api/user/profile` → `member_since` |
| SettingsScreen | "+1 (911) 000-0000" | `GET /api/settings` → `emergency_number` |
| SettingsScreen | SOS message text | `GET /api/settings` → `sos_message` |
| SettingsScreen | "Medium" sensitivity | `GET /api/settings` → `shake_sensitivity` |
| LiveMapScreen | "123 Safety Street..." | `GET /api/location/current` → `address` |
| LiveMapScreen | "40.7128° N, 74.0060° W" | `GET /api/location/current` → `lat/lng` |
| LiveMapScreen | "Sarah Johnson, Michael Chen" | `GET /api/contacts` |
| DashboardScreen | "Raksha Band v1.0" | `GET /api/device/status` → `device_name` |
| HelpSupportScreen | FAQ list | `GET /api/support/faq` |

---

> **This guideline covers every feature visible in the RAKSHA frontend and provides a complete specification for building the Flask backend. Each API endpoint is mapped to its corresponding frontend screen and interaction.**