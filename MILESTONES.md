# Asfalis Safety - Project Milestones

> **Last Updated:** 5 March 2026

## Overview
This document tracks the development progress of the Asfalis Safety backend API, a women's safety application with real-time location tracking, SOS alerts, and trusted contact management.

---

## ✅ Completed Milestones

### Milestone 1: Phone-Based Authentication
**Status:** ✅ Completed  
**Completed Date:** January 2026

**Features Implemented:**
- Phone number-based user registration
- OTP verification for authentication
- JWT token management (access_token and sos_token)
- Session management with token refresh
- Secure password storage with bcrypt hashing
- User profile management

**Technical Stack:**
- Flask-JWT-Extended for token management
- Twilio SMS service for OTP delivery
- PostgreSQL database with SQLAlchemy ORM
- Alembic migrations for schema management

**Endpoints:**
- `POST /api/auth/register` - Register new user with phone
- `POST /api/auth/verify-otp` - Verify OTP and create account
- `POST /api/auth/login` - Login with phone and password
- `POST /api/auth/logout` - Logout and revoke tokens
- `POST /api/auth/refresh` - Refresh access token
- `GET /api/auth/me` - Get current user profile

**Documentation:**
- [API_DOCUMENTATION.md](API_DOCUMENTATION.md#authentication-endpoints)
- [FLASK_API_INTEGRATION.md](FLASK_API_INTEGRATION.md#authentication-flow)

---

### Milestone 2: Trusted Contact Verification System
**Status:** ✅ Completed  
**Completed Date:** 5 March 2026

**Features Implemented:**
- Add trusted contacts with OTP verification
- SMS-based OTP delivery to contact's phone
- Contact verification flow (add → verify OTP → confirmed)
- Resend OTP functionality for failed deliveries
- Idempotent verification (handles already-verified contacts)
- Synchronous SMS delivery with error surfacing
- OTP fallback in API response when SMS delivery fails
- Stale OTP invalidation before issuing a new OTP

**Technical Details:**
- Extended `trusted_contacts` table with `is_verified` and `verified_at` fields
- Added 'trusted_contact_verification' to OTP purpose enum
- Twilio SMS integration (Account 1 — full/paid) for OTP delivery
- Synchronous Twilio calls for OTP paths so errors surface immediately
- `otp_code` included in API response when Twilio cannot deliver (fallback)
- PostgreSQL-compatible enum extension

**Bug Fixes (5 March 2026):**
- Fixed: OTP was sent in background thread → Twilio errors silently swallowed, SMS never delivered
- Fixed: Stale OTPs not invalidated when `add_contact` was called (only `resend-otp` did it)
- Fixed: Wrong Twilio account credentials loaded (env var name mismatch — `TWILIO_ACCOUNT_SID2` vs `TWILIO_ACCOUNT_SID`), causing all SMS to fall through to mock mode
- Fixed: `otp_sent: true` returned even when delivery failed — now reflects actual delivery status

**Endpoints:**
- `POST /api/contacts` - Add new trusted contact (sends OTP)
- `POST /api/contacts/verify-otp` - Verify contact with OTP
- `POST /api/contacts/resend-otp` - Resend OTP to pending contact
- `GET /api/contacts` - List all contacts
- `PUT /api/contacts/<id>` - Update contact details
- `PUT /api/contacts/<id>/primary` - Set as primary contact
- `DELETE /api/contacts/<id>` - Remove a trusted contact

**Database Migration:**
- Migration ID: `e3f4g5h6i7j8_add_contact_verification.py`
- Added verification fields to trusted_contacts table
- Extended otp_purpose_enum with new value

**Testing:**
- ✅ Live testing completed with real phone numbers
- ✅ OTP SMS delivery confirmed via Twilio Account 1 (full/paid)
- ✅ Twilio error 21660 (India A2P block) diagnosed and root cause resolved
- ✅ Contact verified successfully
- ✅ Welcome SMS delivered with WhatsApp instructions

---

### Milestone 3: WhatsApp Integration & Manual SOS Alerts
**Status:** ✅ Completed  
**Completed Date:** 5 March 2026

**Features Implemented:**
- WhatsApp alert delivery via Twilio sandbox (Account 2)
- Manual SOS trigger with real-time location
- "I'm Safe" notification system
- Alert resolution tracking with resolution_type
- Multi-contact WhatsApp broadcast (verified contacts only)
- Debug `test-whatsapp` endpoint for delivery diagnostics
- Dual Twilio account separation (SMS vs WhatsApp)

**Technical Details:**
- Twilio WhatsApp sandbox (Account 2 — Trial) via `+14155238886`
- Twilio SMS (Account 1 — Full/paid) via `+17542407539` for OTPs
- `TWILIO_WA_ACCOUNT_SID` / `TWILIO_WA_AUTH_TOKEN` separate config keys
- Sandbox join code: `join something-popular`
- Added `resolution_type` column to `sos_alerts` table
- Only verified contacts receive SOS WhatsApp alerts

**Bug Fix (5 March 2026):**
- Fixed: Both SMS and WhatsApp were using the same (wrong) Twilio account due to env var naming mismatch
- Separated credentials: Account 1 for SMS, Account 2 for WhatsApp
- Added `TWILIO_WA_ACCOUNT_SID` / `TWILIO_WA_AUTH_TOKEN` to `config.py` and `.env`

**Endpoints:**
- `POST /api/sos/trigger` - Manual SOS trigger (sends WhatsApp)
- `POST /api/sos/send-now` - Dispatch pending alert
- `POST /api/sos/cancel` - Cancel SOS alert
- `POST /api/sos/safe` - Mark user as safe (notify contacts)
- `GET /api/sos/history` - View alert history
- `POST /api/sos/test-whatsapp` - Debug WhatsApp delivery

**WhatsApp Message Format:**
```
🚨 EMERGENCY ALERT 🚨

[User's SOS message]

📍 Location: https://maps.google.com/?q=lat,lng

Sent by Asfalis for [User Name]
```

**"I'm Safe" Message Format:**
```
✅ SAFE: [User Name] is now safe!

They marked themselves safe at [timestamp].

Previous SOS alert has been resolved.

- Asfalis Safety App
```

**Database Migration:**
- Migration ID: `49fa15f2d45d_add_resolution_type_to_sos_alerts.py`
- Added resolution_type field (user_marked_safe, cancelled, timeout, manual_resolution)

**Testing:**
- ✅ Live testing completed with verified contact
- ✅ WhatsApp sandbox joined successfully
- ✅ Manual SOS trigger working (WhatsApp delivered)
- ✅ Emergency location link working
- ✅ "I'm Safe" notifications sent successfully
- ✅ Dual Twilio account split verified and working

---

## 🚧 In Progress Milestones

### Milestone 4: Real-Time Location Tracking
**Status:** 🚧 Partially Implemented  
**Target Date:** Q2 2026

**Planned Features:**
- Socket.IO integration for real-time updates
- Location sharing with trusted contacts
- Location history storage and retrieval
- Privacy controls for location sharing
- Geofencing capabilities

**Current Status:**
- ✅ Socket.IO namespace `/location` implemented (`app/sockets/location_socket.py`)
- ✅ JWT-authenticated socket connections
- ✅ `join_tracking` event — trusted contacts can join a user's tracking room
- ✅ `update_location` event — device pushes GPS coordinates
- ✅ Location service implemented (`app/services/location_service.py`)
- ✅ Location model and history table defined (`app/models/location.py`)
- 🚧 Location broadcast to all tracking contacts not fully wired
- 🚧 Location history management / retention policy not active
- 🚧 Real-time update testing with multiple clients pending

---

### Milestone 5: Advanced SOS Features — Auto SOS & ML Pipeline
**Status:** ✅ Largely Implemented (FCM pending)  
**Target Date:** Q2 2026

**Features Implemented:**
- ✅ Auto-SOS toggle (enable / disable protection mode per user)
- ✅ Sensor data ingestion endpoint (`POST /api/protection/sensor-data`)
- ✅ ML-based danger prediction from sensor windows (`POST /api/protection/predict`)
- ✅ Labeled training data collection (`POST /api/protection/collect`)
- ✅ In-app ML model training trigger (`POST /api/protection/train-model`) — RandomForest, runs in background
- ✅ Model versioning — trained models stored in DB with accuracy score, loaded lazily
- ✅ Auto-SOS trigger fired when ML predicts danger (with 10-min cooldown)
- ✅ Post-event feedback loop — user can correct false alarms (`POST /api/protection/feedback/<alert_id>`), re-labels training data
- ✅ SOS cooldown separation — auto-SOS and manual SOS use independent cooldown timers
- ✅ Settings sync — `auto_sos_enabled` in UserSettings updates in-memory protection cache
- 🚧 FCM push notifications for SOS alerts (model exists, not wired)
- 🚧 Voice/video recording during SOS
- 🚧 Emergency services (112) integration

**Endpoints:**
- `POST /api/protection/toggle` - Enable/disable auto-protection
- `GET /api/protection/status` - Get protection state
- `POST /api/protection/sensor-data` - Push raw sensor reading
- `POST /api/protection/predict` - ML prediction from sensor window → auto-SOS if danger
- `POST /api/protection/collect` - Submit labeled training data
- `POST /api/protection/train-model` - Trigger background model retraining
- `POST /api/protection/feedback/<alert_id>` - False alarm / confirmed danger feedback

**Remaining Work:**
- Wire FCM token to push SOS notification to contacts
- SOS escalation / countdown timer on frontend
- Emergency services integration

---

## 📋 Planned Milestones

### Milestone 6: Device Integration & Sensor Data
**Status:** ✅ Largely Implemented  
**Target Date:** Q3 2026

**Features Implemented:**
- ✅ Device registration and pairing (`POST /api/device/register`)
- ✅ Device status query (`GET /api/device/status`)
- ✅ Device status update (`PUT /api/device/<id>/status`)
- ✅ Hardware-triggered SOS alert endpoint (`POST /api/device/alert`) — API-key style, no JWT
- ✅ Sensor data model and table (`app/models/sensor_data.py`)
- ✅ Sensor data ingestion via protection routes
- ✅ ML model storage in DB (`app/models/ml_model.py`) with versioning
- 🚧 Device health monitoring dashboard
- 🚧 Firmware OTA update mechanism

**Components:**
- Device model (`app/models/device.py`)
- Device routes (`app/routes/device.py`)
- Sensor data model (`app/models/sensor_data.py`)

---

### Milestone 7: Machine Learning Integration
**Status:** ✅ Implemented (accuracy improving with more data)  
**Target Date:** Q3 2026

**Features Implemented:**
- ✅ RandomForest classifier for danger/safe prediction
- ✅ Feature extraction from accelerometer/gyroscope windows (17 features per window)
- ✅ Sliding-window approach — 40 readings per training window
- ✅ Model training endpoint — runs in background thread, stores result in DB
- ✅ Model versioning — each trained model gets a timestamped version, old models deactivated
- ✅ Lazy model loading — loads from DB on first prediction request, falls back to file
- ✅ False alarm feedback loop — re-labels training data, improves future accuracy
- ✅ Accuracy score stored per model version
- 🚧 Offline prediction on device (requires Android ML Kit integration)
- 🚧 Continuous retraining pipeline (cron-triggered)

**Technical Approach:**
- scikit-learn RandomForestClassifier (100 estimators)
- Feature vector: mean, std, min, max, range, energy, correlation (per axis + cross-axis)
- Training data collected per-user and per-sensor-type
- Model stored as joblib-serialised bytes in PostgreSQL

---

### Milestone 8: Protection Features
**Status:** 📋 Planned  
**Target Date:** Q4 2026

**Planned Features:**
- Safe zone/geofence management
- Check-in reminders
- Journey tracking
- Scheduled check-ins
- Auto-alert on check-in miss

**Components:**
- Protection routes exist (`app/routes/protection.py`)
- Protection service defined (`app/services/protection_service.py`)

---

### Milestone 9: Support System
**Status:** 📋 Planned  
**Target Date:** Q4 2026

**Planned Features:**
- In-app support ticket system
- Emergency resource directory
- Safety tips and guidelines
- Community forum integration

**Components:**
- Support model exists (`app/models/support.py`)
- Support routes defined (`app/routes/support.py`)

---

## 🎯 Future Enhancements

### Phase 2 Features (2027)
- [ ] Multi-language support
- [ ] Voice-activated SOS
- [ ] Integration with emergency services (911/112)
- [ ] Wearable device support (smartwatch integration)
- [ ] Community safety mapping
- [ ] Anonymous incident reporting

### Phase 3 Features (Future)
- [ ] AI-powered route safety recommendations
- [ ] Video/audio evidence recording
- [ ] Legal assistance integration
- [ ] Insurance partner integration
- [ ] Enterprise/organization plans

---

## 📊 Technical Metrics

### Current System Stats
- **Total Endpoints:** 35+
- **Database Tables:** 12
- **Migrations:** 5 completed (latest: 49fa15f2d45d)
- **Test Coverage:** Partial (auth, contacts, location, SOS)
- **Documentation Files:** 8 core documents

### Infrastructure
- **Backend:** Python Flask 3.1.0
- **Database:** PostgreSQL (Supabase)
- **SMS/WhatsApp Service:** Twilio (Production - Sandbox for WhatsApp)
- **Push Notifications:** Firebase Cloud Messaging
- **Deployment:** Docker Compose
- **Environment:** Development + Production configs

### Twilio Configuration
- **Account 1 (SMS — Full/Paid):** SID `AC0536...` — used for all OTP SMS delivery
- **Account 2 (WhatsApp — Trial):** SID `ACcb8c...` — used for WhatsApp SOS alerts
- **SMS Number:** `+17542407539`
- **WhatsApp Sandbox Number:** `+14155238886`
- **Sandbox Join Code:** `join something-popular`
- **Note:** India (A2P) SMS blocked on US numbers (error 21660) — resolved by using Account 1 (full/paid)

---

## 🔧 Technical Debt & Improvements

### High Priority
- [ ] Complete test coverage for all endpoints
- [x] Add rate limiting for OTP endpoints *(limiter decorator in place)*
- [ ] Implement comprehensive error logging
- [ ] Add database backup automation
- [ ] Set up CI/CD pipeline
- [x] Fix OTP SMS not delivered to trusted contacts *(fixed 5 March 2026)*
- [x] Surface Twilio errors instead of swallowing in background thread *(fixed 5 March 2026)*
- [x] Separate Twilio SMS and WhatsApp accounts *(fixed 5 March 2026)*

### Medium Priority
- [ ] API documentation auto-generation (Swagger/OpenAPI)
- [ ] Performance monitoring and alerting
- [ ] Database query optimization
- [ ] Caching layer implementation (Redis)
- [ ] API versioning strategy

### Low Priority
- [ ] Code refactoring for better modularity
- [ ] Enhanced API documentation examples
- [ ] Developer onboarding guide
- [ ] Architecture decision records (ADR)

---

## 📞 Contact & Resources

**Project Repository:** `/Users/abhraneelkarmakar/Codes/women_safety_backend`

**Key Documentation:**
- [API_DOCUMENTATION.md](API_DOCUMENTATION.md) - Complete API reference
- [POSTMAN_GUIDE.md](POSTMAN_GUIDE.md) - API testing guide
- [RUN_BACKEND_GUIDE.md](RUN_BACKEND_GUIDE.md) - Setup and run instructions
- [TESTING_GUIDE.md](TESTING_GUIDE.md) - Testing procedures
- [PROJECT_GUIDE.md](PROJECT_GUIDE.md) - Project overview
- [FLASK_API_INTEGRATION.md](FLASK_API_INTEGRATION.md) - Integration guide

---

**Version:** 1.0  
**Maintained by:** Asfalis Safety Development Team  
**Last Review:** 3 March 2026
