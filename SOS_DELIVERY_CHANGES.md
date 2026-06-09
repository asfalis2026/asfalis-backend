# SOS Delivery Changes - Frontend Integration Guide

This document outlines the backend changes made to the SOS alert delivery system. Update your frontend code accordingly.

---

## 1. Removed Status Callback URL

**Change:** Removed the `status_callback` parameter from Twilio WhatsApp message creation.

**Reason:** The `TWILIO_STATUS_CALLBACK_URL` config was missing, causing all SOS alerts to fail.

**Impact:** None for frontend. Status tracking now relies on the delivery report returned after dispatch.

---

## 2. Twilio Error Code 63038 Handling

**Change:** Added Twilio error code `63038` to error mapping — maps to `"rate_limited"` status.

**File:** `app/services/whatsapp_service.py`

```python
_SANDBOX_ERRORS = {
    ...
    63038: "rate_limited",  # Daily message limit exceeded
}
```

**What this means:**
- When the Twilio sandbox exceeds 50 messages/day, error 63038 is returned
- Backend now correctly identifies this as `"rate_limited"` instead of generic `"delivery_failed"`
- Frontend will receive `"rate_limited"` in the delivery report

---

## 3. Individual Contact Delivery Status

**Change:** Each emergency contact now returns their own delivery status with their name.

**Response Format:**

```json
{
  "success": true,
  "message": "SOS Dispatched via WhatsApp",
  "data": {
    "delivery_report": [
      {
        "phone": "+9199xxx",
        "contact_name": "John",
        "delivered": true,
        "status": "✅ Message sent",
        "twilio_sid": "SMxxx",
        "error_code": null
      },
      {
        "phone": "+9198xxx",
        "contact_name": "Jane",
        "delivered": false,
        "status": "❌ Contact not in WhatsApp sandbox (they need to text 'join' to the sandbox number)",
        "twilio_sid": null,
        "error_code": 63016
      },
      {
        "phone": "+9197xxx",
        "contact_name": "Bob",
        "delivered": true,
        "status": "✅ Message sent",
        "twilio_sid": "SMxxx",
        "error_code": null
      }
    ],
    "status": "sent"
  }
}
```

### Fields in `delivery_report`:

| Field | Type | Description |
|-------|------|-------------|
| `phone` | string | Contact's phone number |
| `contact_name` | string | Contact's name from trusted contacts |
| `delivered` | boolean | Whether message was sent successfully |
| `status` | string | Human-readable status message |
| `twilio_sid` | string | Twilio message SID (if sent) |
| `error_code` | integer | Twilio error code (if failed) |

### Possible Status Values:

| Status Display | Meaning |
|----------------|---------|
| `✅ Message sent` | Message sent successfully |
| `❌ Contact not in WhatsApp sandbox` | Contact must text "join" to sandbox number |
| `❌ Contact hasn't opted in to receive messages` | Contact needs to opt-in |
| `❌ Twilio sandbox daily limit exceeded` | Twilio 50-msg/day limit reached |
| `❌ Twilio not configured` | Backend misconfiguration |
| `❌ Failed: <error>` | Generic failure with error message |

---

## 4. Max Trusted Contacts

**Note:** Each account can have **maximum 3 emergency contacts**. The backend enforces this limit when adding new trusted contacts.

---

## Summary for UI Updates

1. **Display each contact's status separately** — iterate over `delivery_report` array
2. **Show contact name** — use the `contact_name` field for display
3. **Show individual delivery status** — use the `status` field or `delivered` boolean
4. **Handle rate limit gracefully** — show upgrade prompt when `status` contains "daily limit exceeded"
5. **Show contact order** — contacts are returned in the order they were added (Contact 1, 2, 3)
