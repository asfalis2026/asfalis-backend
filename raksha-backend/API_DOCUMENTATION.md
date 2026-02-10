# Raksha Backend API Documentation

Base URL: `http://localhost:5000/api`

## Table of Contents
1. [Authentication](#authentication)
2. [User Profile](#user-profile)
3. [Trusted Contacts](#trusted-contacts)
4. [SOS & Alerts](#sos--alerts)
5. [Location](#location)
6. [Devices](#devices)
7. [Protection](#protection)
8. [Settings](#settings)
9. [Support](#support)

---

## Authentication

### Register (Email)
- **Endpoint**: `/auth/register/email`
- **Method**: `POST`
- **Body**:
  ```json
  {
    "email": "user@example.com",
    "password": "strongpassword123",
    "full_name": "John Doe"
  }
  ```
- **Response**: `201 Created`

### Login (Email)
- **Endpoint**: `/auth/login/email`
- **Method**: `POST`
- **Body**:
  ```json
  {
    "email": "user@example.com",
    "password": "strongpassword123"
  }
  ```
- **Response**: `200 OK` (Returns `access_token` and `refresh_token`)

### Send OTP (Phone Login)
- **Endpoint**: `/auth/send-otp`
- **Method**: `POST`
- **Body**:
  ```json
  {
    "phone": "+1234567890"
  }
  ```

### Verify OTP
- **Endpoint**: `/auth/verify-otp`
- **Method**: `POST`
- **Body**:
  ```json
  {
    "phone": "+1234567890",
    "otp_code": "123456"
  }
  ```
- **Response**: `200 OK` (Returns tokens)

### Refresh Token
- **Endpoint**: `/auth/refresh`
- **Method**: `POST`
- **Headers**: `Authorization: Bearer <refresh_token>`

---

## User Profile
**Headers**: `Authorization: Bearer <access_token>`

### Get Profile
- **Endpoint**: `/user/profile`
- **Method**: `GET`

### Update Profile
- **Endpoint**: `/user/profile`
- **Method**: `PUT`
- **Body**:
  ```json
  {
    "full_name": "Jane Doe",
    "phone": "+9876543210"
  }
  ```

### Update FCM Token
- **Endpoint**: `/user/fcm-token`
- **Method**: `PUT`
- **Body**:
  ```json
  {
    "fcm_token": "device_token_string"
  }
  ```

---

## Trusted Contacts

### Get Contacts
- **Endpoint**: `/contacts`
- **Method**: `GET`

### Add Contact
- **Endpoint**: `/contacts`
- **Method**: `POST`
- **Body**:
  ```json
  {
    "name": "Mom",
    "phone": "+19876543210",
    "relationship": "Parent",
    "is_primary": true
  }
  ```

### Update Contact
- **Endpoint**: `/contacts/<id>`
- **Method**: `PUT`
- **Body**: `{"name": "Mother"}`

### Delete Contact
- **Endpoint**: `/contacts/<id>`
- **Method**: `DELETE`

---

## SOS & Alerts

### Trigger SOS
- **Endpoint**: `/sos/trigger`
- **Method**: `POST`
- **Body**:
  ```json
  {
    "latitude": 40.7128,
    "longitude": -74.0060,
    "trigger_type": "manual" 
  }
  ```
- **Note**: `trigger_type` can be `manual`, `voice`, `shake`, `fall`.

### Cancel SOS
- **Endpoint**: `/sos/cancel`
- **Method**: `POST`
- **Body**: `{"alert_id": "uuid-string"}`

### Get SOS History
- **Endpoint**: `/sos/history`
- **Method**: `GET`

---

## Location

### Update Location
- **Endpoint**: `/location/update`
- **Method**: `POST`
- **Body**:
  ```json
  {
    "latitude": 40.7128,
    "longitude": -74.0060,
    "accuracy": 10.5,
    "is_sharing": true
  }
  ```

### Get Current Location (Last Known)
- **Endpoint**: `/location/current`
- **Method**: `GET`

### Start Live Sharing
- **Endpoint**: `/location/share/start`
- **Method**: `POST`
- **Response**: Returns a public tracking URL.

### Stop Live Sharing
- **Endpoint**: `/location/share/stop`
- **Method**: `POST`

---

## Devices (Smart Jewelry/Band)

### Register Device
- **Endpoint**: `/device/register`
- **Method**: `POST`
- **Body**:
  ```json
  {
    "device_name": "Raksha Band",
    "device_mac": "AA:BB:CC:11:22:33"
  }
  ```

### Get Device Status
- **Endpoint**: `/device/status`
- **Method**: `GET`

### Update Device Status
- **Endpoint**: `/device/<id>/status`
- **Method**: `PUT`
- **Body**: `{"is_connected": true}`

### Device Alert (Hardware Trigger)
- **Endpoint**: `/device/alert`
- **Method**: `POST`
- **Body**: `{"device_mac": "AA:BB:CC:11:22:33"}`
- **Note**: Triggers SOS based on device MAC.

---

## Protection (Modes)

### Toggle Protection Mode
- **Endpoint**: `/protection/toggle`
- **Method**: `POST`
- **Body**: `{"is_active": true}`

### Get Protection Status
- **Endpoint**: `/protection/status`
- **Method**: `GET`

---

## Settings

### Get User Settings
- **Endpoint**: `/settings`
- **Method**: `GET`

### Update Settings
- **Endpoint**: `/settings`
- **Method**: `PUT`
- **Body**:
  ```json
  {
    "emergency_number": "911",
    "shake_sensitivity": 5
  }
  ```

---

## Support

### Get FAQs
- **Endpoint**: `/support/faq`
- **Method**: `GET`

### Create Ticket
- **Endpoint**: `/support/ticket`
- **Method**: `POST`
- **Body**:
  ```json
  {
    "subject": "App Issue",
    "message": "The app crashes when I open settings."
  }
  ```
