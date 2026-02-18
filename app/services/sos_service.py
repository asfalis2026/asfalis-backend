
from app.extensions import db
from app.models.sos_alert import SOSAlert
from app.models.trusted_contact import TrustedContact
from app.models.user import User
from app.services.sms_service import send_sms
from app.services.fcm_service import send_push_notification 
from datetime import datetime, timedelta

COUNTDOWN_EXPIRY_SECONDS = 60  # Auto-expire stale countdown alerts after 60s

def trigger_sos(user_id, lat, lng, trigger_type='manual'):
    # Enforce 20-second cooldown across all SOS triggers (manual + sensor)
    from app.services.protection_service import _is_on_cooldown, _mark_sos_triggered
    if _is_on_cooldown(user_id):
        existing = SOSAlert.query.filter_by(user_id=user_id, status='countdown').first()
        if existing:
            return existing, "SOS on cooldown — please wait 20 seconds between triggers."
        return None, "SOS on cooldown — please wait 20 seconds between triggers."

    user = User.query.get(user_id)
    if not user:
        return None, "User not found"

    # Check for existing countdown alert
    existing_alert = SOSAlert.query.filter_by(
        user_id=user_id, status='countdown'
    ).first()
    
    if existing_alert:
        # Auto-cancel stale countdowns (older than 60s)
        if existing_alert.triggered_at and \
           (datetime.utcnow() - existing_alert.triggered_at).total_seconds() > COUNTDOWN_EXPIRY_SECONDS:
            existing_alert.status = 'cancelled'
            existing_alert.resolved_at = datetime.utcnow()
            db.session.commit()
        else:
            return existing_alert, "Alert already in countdown"

    # Prioritize the new sos_message on User model, fallback to Settings or Default
    start_message = "Emergency!"
    if user.sos_message:
        start_message = user.sos_message
    elif user.settings and user.settings.sos_message:
        start_message = user.settings.sos_message
    
    sos_message = start_message

    new_alert = SOSAlert(
        user_id=user_id,
        trigger_type=trigger_type,
        latitude=lat,
        longitude=lng,
        status='countdown',
        sos_message=sos_message,
        contacted_numbers=[]
    )
    db.session.add(new_alert)
    db.session.commit()

    # Mark cooldown for this user
    _mark_sos_triggered(user_id)

    # Auto-dispatch: immediately send SMS + WhatsApp to all contacts
    dispatch_sos(new_alert.id)
    
    return new_alert, "SOS triggered and messages sent"

def dispatch_sos(alert_id):
    alert = SOSAlert.query.get(alert_id)
    if not alert:
        return False, "Alert not found"
    
    if alert.status == 'resolved' or alert.status == 'cancelled':
        return False, "Alert already resolved/cancelled"

    user = User.query.get(alert.user_id)
    contacts = TrustedContact.query.filter_by(user_id=user.id).all()

    alert.status = 'sent'
    alert.sent_at = datetime.utcnow()
    
    contacted = []
    
    # Generate Google Maps Link
    maps_link = f"https://maps.google.com/?q={alert.latitude},{alert.longitude}"
    full_message = f"{alert.sos_message}\n\n📍 Location: {maps_link}\nSent by Asfalis for {user.full_name}"

    for contact in contacts:
        # Send SMS
        send_sms(contact.phone, full_message)
        contacted.append(contact.phone)

        # Send WhatsApp alert
        try:
            from app.services.whatsapp_service import send_whatsapp_alert
            send_whatsapp_alert(contact.phone, full_message)
        except Exception as e:
            print(f"WhatsApp alert to {contact.phone} failed: {e}")
    
    alert.contacted_numbers = contacted
    db.session.commit()
    
    return True, "SOS Dispatched"

def cancel_sos(alert_id):
    alert = SOSAlert.query.get(alert_id)
    if not alert:
        return False, "Alert not found"

    if alert.status == 'sent':
         # If already sent, we might want to send a "Safe now" message
         pass

    alert.status = 'cancelled'
    alert.resolved_at = datetime.utcnow()
    db.session.commit()
    return True, "SOS Cancelled"
