# Android Handoff: Twilio Sandbox Rate Limiting Fix

**Date:** June 6, 2026
**Backend PR:** Implements failed status tracking for SOS dispatches

---

## Problem

Previously, when Twilio Sandbox daily message limit was exceeded, the backend would report success but the messages wouldn't actually be sent. Users were misinformed about their SOS being delivered.

## Solution

The backend now properly detects and reports failures when Twilio messages cannot be sent.

---

## API Changes

### 1. `POST /api/sos/send-now` Response

**New field:** `status` in response data

```json
// Success case
{
  "success": true,
  "message": "SOS Dispatched via WhatsApp",
  "data": {
    "delivery_report": [...],
    "status": "sent"
  }
}

// Failure case (rate limit / sandbox exceeded)
{
  "success": true,
  "message": "SOS dispatch failed - Twilio sandbox daily message limit exceeded! Please upgrade to a Twilio paid account for unlimited WhatsApp messages.",
  "data": {
    "delivery_report": [...],
    "status": "failed"
  }
}
```

### 2. `GET /api/sos/history` Response

**New field:** `status` now includes `"failed"` as a possible value

```json
{
  "success": true,
  "data": [
    {
      "alert_id": "...",
      "status": "failed",        // ← Can now be "failed"
      "trigger_type": "manual",
      "triggered_at": "2026-06-06T14:30:00",
      "resolution_type": null
    }
  ]
}
```

---

## Android App Changes Required

### 1. Handle `"failed"` Status

In your SOS history view / alert list:

```kotlin
// Example Kotlin
when (alert.status) {
    "sent" -> showGreenBadge("Sent")
    "countdown" -> showYellowBadge("Countdown")
    "cancelled" -> showGrayBadge("Cancelled")
    "failed" -> showRedBadge("FAILED")  // ← NEW
    "resolved" -> showGreenBadge("Resolved")
}
```

### 2. Handle `/send-now` Response

Check the `status` field in the response:

```kotlin
val response = api.sendSosNow(alertId)
if (response.data.status == "failed") {
    // Show error message to user
    showErrorDialog(response.message)
}
```

### 3. User-Friendly Error Messages

When `status == "failed"`, show these messages to users:

| Message Contains | User Message |
|-----------------|--------------|
| "Twilio sandbox daily limit exceeded" | "Daily message limit exceeded. Please try again tomorrow or upgrade to premium." |
| "not_in_sandbox" | "One or more contacts haven't joined the WhatsApp sandbox. Ask them to send 'join something-popular' to WhatsApp." |
| "not_opted_in" | "One or more contacts need to opt-in to WhatsApp. Ask them to send 'join something-popular' to WhatsApp." |

---

## Testing

### Test Rate Limit

1. Trigger many SOS alerts in quick succession
2. Or use Twilio test credentials with low limits
3. Verify the app shows "FAILED" badge

### Test Normal Flow

1. Trigger SOS with valid contacts
2. Verify "sent" status is returned
3. Verify green badge is shown

---

## Database Changes

| Column | Type | Description |
|--------|------|-------------|
| `status` | enum | Added `"failed"` value |
| `message_sids` | JSON | Stores Twilio message SIDs for debugging |

---

## Questions?

Contact: Backend Team
