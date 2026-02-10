
from app.extensions import db
from app.models.sos_alert import SOSAlert
from app.models.trusted_contact import TrustedContact
from app.models.user import User
from app.services.sms_service import send_sms
from app.services.fcm_service import send_push_notification 
from datetime import datetime

def trigger_sos(user_id, lat, lng, trigger_type='manual'):
    user = User.query.get(user_id)
    if not user:
        return None, "User not found"

    # Create Alert
    existing_alert = SOSAlert.query.filter_by(
        user_id=user_id, status='countdown'
    ).first()
    
    if existing_alert:
        return existing_alert, "Alert already in countdown"

    sos_message = user.settings.sos_message if user.settings else "Emergency!"

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

    # In a real app, we'd start a Celery task here for countdown
    # For now, we assume frontend manages countdown UI and calls 'send-now'
    
    return new_alert, "Countdown started"

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
    full_message = f"{alert.sos_message}\n\n📍 Location: {maps_link}\nSent by RAKSHA for {user.full_name}"

    for contact in contacts:
        # Send SMS
        send_sms(contact.phone, full_message)
        contacted.append(contact.phone)
        
        # In a real app, we would check if contact is also a user and send Push Notif
    
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
