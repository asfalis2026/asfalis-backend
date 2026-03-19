# User Authentication & Contact Security

Asfalis implements a robust, multi-layered security system focused on **Identity Assurance** and **Device Trust**. This document details how we handle user verification and the secure addition of emergency contacts.

---

## 🛡️ 1. Authentication Infrastructure

Asfalis uses **JWT (JSON Web Tokens)** with a three-token system to balance security and availability.

### Token Types
1.  **Access Token (15 min)**: Used for all standard API calls (profile updates, settings). Short-lived to minimize damage if stolen.
2.  **Refresh Token (Long-lived)**: Used to fetch new access tokens. Implements **Refresh Token Rotation**—each time it's used, the old one is revoked (`revoked_tokens` table) and a new one is issued.
3.  **SOS Token (30 Days)**: A specialized, long-lived access token stored securely by the Android app. It is used **only** for the `/sos/trigger` endpoint. This ensures that even if the session has expired, an emergency alert can still be sent instantly.

### Password Security
Passwords are never stored in plain text. We use **Bcrypt** with a salt factor of 12 to hash passwords before storage in Supabase.
```python
hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
```

---

## ⌚ 2. Handset Change Security (IMEI Binding)

To prevent account takeovers, Asfalis binds each user account to a specific physical device via its **IMEI (International Mobile Equipment Identity)**.

### The 12-Hour Security Window
If a user tries to log in from a new device:
1.  The system detects the new IMEI and blocks the login.
2.  A `HandsetChangeRequest` is created in the database.
3.  A **12-hour "Cool-off"** period begins. This gives the legitimate owner time to receive a notification and block the transfer if it wasn't them.
4.  After 12 hours, the user can re-attempt login with `confirm_handover=true` to bind the new device.

---

## 👥 3. Trusted Contact Addition (OTP Flow)

Adding an emergency contact is a two-step verification process. This ensures that the person being added is aware and their phone number is correct.

### Step 1: Initiation
The user submits the contact's name and phone number.
-   The system creates a `TrustedContact` record with `is_verified=False`.
-   A 6-digit **OTP** is generated and sent via Twilio SMS to the *contact's* phone.

### Step 2: Verification
The contact gives the OTP to the user, who submits it to the backend.
-   Upon successful verification, the contact is marked as `is_verified=True`.
-   **Welcome Notification**: A final WhatsApp message is sent to the contact with instructions on how to join the Asfalis Sandbox for future emergency alerts.

### Code Snippet: Contact OTP Generation
```python
# app/routes/contacts.py
otp_code = str(random.randint(100000, 999999))
# Store OTP with 'trusted_contact_verification' purpose
otp_record = OTPRecord(phone=phone, otp_code=otp_code, purpose='trusted_contact_verification')
# Synchronous SMS dispatch
sms_ok, detail = send_contact_verification_otp(phone, otp_code)
```

---

## 🏁 4. Theory Concepts

### Zero Trust Interaction
We assume the network is hostile. This is why **Refresh Token Rotation** is critical; if an attacker steals a refresh token, they only get one use before it's invalidated. If the legitimate user also tries to refresh, the "reused" status triggers a security alert and logs out all sessions.

### Rate Limiting
To prevent brute-forcing OTPs or passwords, sensitive endpoints (Login, Resend OTP) use **Flask-Limiter**:
-   **Login**: 5 attempts per 15 minutes.
-   **OTP Resend**: 3 attempts per 15 minutes.

### Verified Delivery
Unlike standard SMS, our WhatsApp notifications use **Delivery Reports**. If a contact hasn't joined the sandbox or their number is invalid, the backend captures the specific Twilio error code and notifies the user in the "Dispatch Report" so they can choose an alternative contact.
