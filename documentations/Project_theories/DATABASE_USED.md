# Database Schema: Asfalis Backend

This document provides a detailed breakdown of the PostgreSQL database schema used in the Asfalis project. The database is hosted on **Supabase** and managed via **SQLAlchemy** and **Alembic** migrations.

---

## 🏗️ Table Definitions

### 1. `users`
The central table storing user account information.
- **`id`** (String 36, PK): Unique UUID.
- **`full_name`** (String 100, Not Null): User's legal name.
- **`country`** (String 100): User's country (used for emergency numbers and timezones).
- **`phone`** (String 20, Unique): E.164 formatted phone number.
- **`email`** (String 255, Unique): Optional email address.
- **`password_hash`** (String 255): Bcrypt hashed password.
- **`auth_provider`** (Enum): `phone` or `google`.
- **`is_verified`** (Boolean): True if phone OTP verification is complete.
- **`sos_message`** (String 500): Custom fallback SOS message.
- **`fcm_token`** (String 500): Firebase Cloud Messaging token for push notifications.
- **`created_at`** / **`updated_at`** (DateTime): Timestamps for record management.

### 2. `trusted_contacts`
Emergency contacts designated by users.
- **`id`** (String 36, PK): Unique UUID.
- **`user_id`** (String 36, FK): Reference to `users.id`.
- **`name`** (String 100, Not Null): Contact's display name.
- **`phone`** (String 20, Not Null): E.164 formatted phone number.
- **`email`** (String 255): Optional contact email.
- **`relationship`** (String 50): Relationship to the user (e.g., "Parent", "Friend").
- **`is_primary`** (Boolean): Indicates if this is the main contact to be notified first.
- **`is_verified`** (Boolean): True if the contact has been verified (v1 OTP flow).
- **`verified_at`** (DateTime): Timestamp of verification success.

### 3. `sos_alerts`
Records of all triggered emergency alerts.
- **`id`** (String 36, PK): Unique UUID.
- **`user_id`** (String 36, FK): Reference to `users.id`.
- **`trigger_type`** (Enum): `manual`, `auto_fall`, `auto_shake`, `bracelet`, `iot_button`.
- **`latitude`** / **`longitude`** (Float, Not Null): GPS coordinates at trigger time.
- **`address`** (String 500): Resolved human-readable address.
- **`status`** (Enum): `countdown`, `sent`, `cancelled`, `resolved`.
- **`sos_message`** (Text, Not Null): The actual message content dispatched.
- **`contacted_numbers`** (JSON): Audit trail of phone numbers notified.
- **`trigger_reason`** (Text): Automated triggers only; explains the sensor detection.
- **`resolution_type`** (String): `user_marked_safe`, `cancelled`, `timeout`, `expired`.
- **`triggered_at`** / **`sent_at`** / **`resolved_at`** (DateTime): Event lifecycle timestamps.

### 4. `location_history`
Historical tracking of user movements.
- **`id`** (String 36, PK): Unique UUID.
- **`user_id`** (String 36, FK): Reference to `users.id`.
- **`latitude`** / **`longitude`** (Float, Not Null): Movement coordinates.
- **`address`** (String 500): Optional reverse-geocoded address.
- **`accuracy`** (Float): Precision of the GPS fix.
- **`is_sharing`** (Boolean): Flag for active real-time sharing.
- **`recorded_at`** (DateTime): Timestamp of the reading.

### 5. `connected_devices`
Hardware sensors and IoT bracelets paired with the user.
- **`id`** (String 36, PK): Unique UUID.
- **`user_id`** (String 36, FK): Reference to `users.id`.
- **`device_name`** (String 100, Not Null): User-friendly label.
- **`device_mac`** (String 17, Not Null): Hardware MAC address.
- **`is_connected`** (Boolean): Current connectivity status.
- **`battery_level`** (Integer): Last reported battery percentage.
- **`last_seen`** (DateTime): Last heartbeat from the device.
- **`last_button_press_at`** (DateTime): Used for IoT double-tap (Cancel) logic.

### 6. `user_settings`
User-specific application preferences.
- **`user_id`** (String 36, FK, Unique): Reference to `users.id`.
- **`emergency_number`** (String 20): Local emergency service number (e.g., "112", "911").
- **`sos_message`** (Text): Default template for emergency alerts.
- **`shake_sensitivity`** (Enum): `low`, `medium`, `high`.
- **`auto_sos_enabled`** (Boolean, Not Null): Master toggle for ML-powered protection.
- **`haptic_feedback`** (Boolean): Toggle for on-device vibrations.

### 7. `otp_records` (referred to as `op_records`)
Short-lived records for One-Time Password verification.
- **`id`** (String 36, PK): Unique UUID.
- **`phone`** (String 20): Target phone number.
- **`otp_code`** (String 6, Not Null): The 6-digit code.
- **`purpose`** (Enum): `login`, `verify`, `reset_password`, `phone_verification`, `trusted_contact_verification`.
- **`attempts`** (Integer): Security counter for brute-force prevention.
- **`is_used`** (Boolean): Flag to prevent token reuse.
- **`expires_at`** (DateTime): Expiration timestamp (typically 5 minutes).

### 8. `sensor_training_data`
Raw and labeled sensor data used for Machine Learning.
- **`id`** (String 36, PK): Unique UUID.
- **`user_id`** (String 36, FK): Reference to `users.id`.
- **`sensor_type`** (String 20): `accelerometer` or `gyroscope`.
- **`x`, `y`, `z`** (Float): Axis-specific motion data.
- **`timestamp`** (BigInteger): Unix epoch in milliseconds.
- **`label`** (Integer): `0` (Safe) or `1` (Danger).
- **`is_verified`** (Boolean): True if data was manually labeled via user feedback.

### 9. `ml_models`
Serialized ML model versions for inferred danger detection.
- **`id`** (String 36, PK): Unique UUID.
- **`version`** (String 20): Model iteration identifier.
- **`is_active`** (Boolean): Indicates the current "live" model.
- **`data`** (LargeBinary): The pickled Scikit-learn model object.
- **`accuracy`** (Float): Performance score at the time of training.

### 10. `user_device_bindings`
Hardware binding to strictly limit account access to a single handset.
- **`user_id`** (String 36, FK, Unique): Reference to `users.id`.
- **`device_imei`** (String 64, Not Null): Handset IMEI/Unique ID.
- **`last_login_at`** (DateTime): Security audit field.

### 11. `handset_change_requests`
Audit log for security-delayed handset transfers.
- **`user_id`** (String 36, FK): Reference to `users.id`.
- **`old_device_imei`** / **`new_device_imei`** (String 64): Transfer details.
- **`status`** (String 20): `pending`, `completed`, `rejected`, `expired`.
- **`eligible_at`** (DateTime): Timestamp when the 12-hour security delay expires.

### 12. `revoked_tokens`
Security blacklist for JWT refresh tokens.
- **`jti`** (String 36, Unique, Index): The unique ID of the revoked token.
- **`token_type`** (String 20): Always `refresh` in current implementation.
- **`revoked_at`** (DateTime): Timestamp of logout or rotation.

### 13. `support_tickets`
User support and ticket management.
- **`user_id`** (String 36, FK): Reference to `users.id`.
- **`subject`** / **`message`** (String/Text): Ticket content.
- **`status`** (Enum): `open`, `in_progress`, `resolved`.

### 14. `alembic_version`
Internal Alembic table used to track the current database migration revision.
- **`version_num`** (String 32, PK): The ID of the latest successful migration.

---

## 🚀 Advanced Architecture Tables (v2)

These tables are defined in the **v2 Architecture** (Bidirectional Linking & FCM) as referenced in the system's technical documentation and Postman guides.

### 15. `temp_device_codes`
Used for bidirectional, secure contact linking without sharing OTPs or phone numbers.
- **`id`** (UUID/String): Unique ID.
- **`user_id`** (FK): The user who generated the code (User A).
- **`code`** (char 6): The 6-character alphanumeric pairing code.
- **`expires_at`** (DateTime): Code validity window (typically 10 minutes).
- **`is_used`** (Boolean): Flag to ensure single-use pairing.

### 16. `received_sos_alerts`
Tracks alerts received by emergency contacts for centralized coordination.
- **`alert_id`** (FK): Reference to the original `sos_alerts.id`.
- **`receiver_id`** (FK): Reference to `users.id` (the emergency contact).
- **`received_at`** (DateTime): When the push notification was dispatched.
- **`is_read`** (Boolean): Tracks if the receiver has opened the alert details.
