# Raksha Backend - Testing Guide

This guide provides `curl` commands to test the Raksha Backend API running locally at `http://localhost:5000`.

## 1. Environment Setup

Assign the API URL to a variable for easier testing:

```bash
export API_URL="http://localhost:5000/api"
```

## 2. Authentication Flow (Get Token)

First, register a user to get an `access_token`.

### Register User
```bash
curl -X POST "$API_URL/auth/register/email" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "password123",
    "full_name": "Test User"
  }'
```

**Copy the `access_token` from the response** and export it:

```bash
export TOKEN="<PASTE_YOUR_ACCESS_TOKEN_HERE>"
```

### Login (If already registered)
```bash
curl -X POST "$API_URL/auth/login/email" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "password123"
  }'
```

---

## 3. Testing Protected Endpoints

Use the `$TOKEN` variable in the header for all subsequent requests.

### User Profile
```bash
# Get Profile
curl -X GET "$API_URL/user/profile" -H "Authorization: Bearer $TOKEN"

# Update Profile
curl -X PUT "$API_URL/user/profile" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"full_name": "Updated Name", "phone": "+15550001111"}'
```

### Trusted Contacts
```bash
# Add Contact
curl -X POST "$API_URL/contacts" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Dad",
    "phone": "+15551234567",
    "relationship": "Parent",
    "is_primary": true
  }'

# Get Contacts
curl -X GET "$API_URL/contacts" -H "Authorization: Bearer $TOKEN"
```

### SOS Alert 🚨
```bash
# Trigger SOS (Manual)
curl -X POST "$API_URL/sos/trigger" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "latitude": 37.7749,
    "longitude": -122.4194,
    "trigger_type": "manual"
  }'
```

### Location Sharing
```bash
# Update Location
curl -X POST "$API_URL/location/update" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "latitude": 37.7749,
    "longitude": -122.4194,
    "is_sharing": true
  }'
```

### Device Management
```bash
# Register Mock Device
curl -X POST "$API_URL/device/register" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "device_name": "Raksha Band V1",
    "device_mac": "00:11:22:33:44:55"
  }'
```

### Settings
```bash
# Get Settings
curl -X GET "$API_URL/settings" -H "Authorization: Bearer $TOKEN"

# Update Settings
curl -X PUT "$API_URL/settings" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"shake_sensitivity": 8}'
```

---

## 4. Resetting Data

To start fresh, simply delete the SQLite database file and re-run migrations:

```bash
rm instance/raksha.db
flask db upgrade
```
