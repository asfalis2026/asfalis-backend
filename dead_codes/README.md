# Dead Code

This folder contains code that was removed from the main codebase but kept for reference.

## Files

### 1. unused_sms_functions.py
- `send_otp_via_verify()` - Was for Twilio Verify API, never implemented
- `check_otp_via_verify()` - Was for Twilio Verify API, never implemented
- `send_sos_sms()` - Was for SMS-based SOS (replaced by WhatsApp)
- `send_contact_welcome_sms()` - Replaced by in-app sandbox instructions

### 2. unused_whatsapp_functions.py
- `send_whatsapp_alert()` - Fire-and-forget variant, never used

### 3. unused_sos_functions.py
- `_get_configured_cooldown()` - Never called, hardcoded values used instead

## Why These Are Here

These functions are kept for:
1. Historical reference
2. Potential future implementation
3. Understanding the codebase evolution

They are NOT imported or used anywhere in the app.
