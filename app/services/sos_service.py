from flask import current_app

from app.extensions import db
from app.models.sos_alert import SOSAlert
from app.models.trusted_contact import TrustedContact
from app.models.user import User
from app.services.fcm_service import send_push_notification 
from app.utils.timezone_utils import format_datetime_for_display
from datetime import datetime
import logging

COUNTDOWN_EXPIRY_SECONDS = 60  # Auto-expire stale countdown alerts after 60s


def _get_configured_cooldown():
    """Fetch SOS cooldown override from app config if available."""
    try:
        value = current_app.config.get('SOS_COOLDOWN_SECONDS')
    except RuntimeError:
        return None

    if value is None:
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None

def trigger_sos(user_id, lat, lng, trigger_type='manual'):
    # Enforce cooldown across all SOS triggers (manual + sensor)
    from app.services.protection_service import _is_on_cooldown, _mark_sos_triggered, SOS_COOLDOWN_SECONDS

    cooldown_seconds = _get_configured_cooldown()
    wait_window = cooldown_seconds if cooldown_seconds is not None else SOS_COOLDOWN_SECONDS

    if _is_on_cooldown(user_id, cooldown_seconds):
        existing = SOSAlert.query.filter_by(user_id=user_id, status='countdown').first()
        if existing:
            return existing, f"SOS on cooldown — please wait {wait_window} seconds between triggers."
        return None, f"SOS on cooldown — please wait {wait_window} seconds between triggers."

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

    # Do NOT auto-dispatch here. Client controls countdown state and decides:
    # - send-now on timeout / navigate home
    # - mark safe for false alarm
    return new_alert, "SOS countdown started"

def dispatch_sos(alert_id, user_id=None):
    alert = SOSAlert.query.get(alert_id)
    if not alert:
        return False, "Alert not found"

    if user_id and alert.user_id != user_id:
        return False, "Unauthorized: This alert does not belong to you"
    
    if alert.status in ['resolved', 'cancelled']:
        return False, "Alert already resolved/cancelled"

    if alert.status == 'sent':
        return True, "SOS already dispatched"

    if alert.status != 'countdown':
        return False, f"Alert cannot be dispatched from state: {alert.status}"

    user = User.query.get(alert.user_id)
    contacts = TrustedContact.query.filter_by(user_id=user.id, is_verified=True).all()

    alert.status = 'sent'
    alert.sent_at = datetime.utcnow()
    
    contacted = []
    
    # Generate Google Maps Link
    maps_link = f"https://maps.google.com/?q={alert.latitude},{alert.longitude}"
    full_message = f"🚨 EMERGENCY ALERT 🚨\n\n{alert.sos_message}\n\n📍 Location: {maps_link}\n\nSent by Asfalis for {user.full_name}"

    # Only send WhatsApp (no SMS to reduce costs)
    for contact in contacts:
        contacted.append(contact.phone)
        
        # Send WhatsApp alert only
        try:
            from app.services.whatsapp_service import send_whatsapp_alert
            send_whatsapp_alert(contact.phone, full_message)
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"WhatsApp alert to {contact.phone} failed: {e}")
    
    alert.contacted_numbers = contacted
    db.session.commit()
    
    return True, "SOS Dispatched via WhatsApp"

def cancel_sos(alert_id, user_id=None):
    alert = SOSAlert.query.get(alert_id)
    if not alert:
        return False, "Alert not found"

    if user_id and alert.user_id != user_id:
        return False, "Unauthorized: This alert does not belong to you"

    if alert.status == 'sent':
         # If already sent, we might want to send a "Safe now" message
         pass

    alert.status = 'cancelled'
    alert.resolved_at = datetime.utcnow()
    alert.resolution_type = 'cancelled'
    db.session.commit()
    return True, "SOS Cancelled"


def mark_user_safe(alert_id, user_id):
    """
    Mark user as safe and send WhatsApp notifications to all verified contacts.
    
    Args:
        alert_id: The SOS alert ID
        user_id: The authenticated user ID (for verification)
    
    Returns:
        tuple: (success: bool, message: str, contacts_notified: int)
    """
    alert = SOSAlert.query.get(alert_id)
    
    # Validation checks
    if not alert:
        return False, "Alert not found", 0
    
    # Verify alert belongs to the authenticated user
    if alert.user_id != user_id:
        return False, "Unauthorized: This alert does not belong to you", 0
    
    # Check if alert is already resolved
    if alert.status in ['cancelled', 'resolved']:
        return False, f"This alert has already been resolved (status: {alert.status})", 0
    
    # If status is 'safe', return success but indicate already marked
    if alert.resolution_type == 'user_marked_safe':
        return True, "Alert already marked as safe", 0
    
    # State transition rules for false alarms:
    # - countdown -> cancelled (no contacts were notified)
    # - sent -> cancelled (safe update should notify contacts)
    notify_contacts = alert.status == 'sent'

    alert.status = 'cancelled'
    alert.resolved_at = datetime.utcnow()
    alert.resolution_type = 'false_alarm'
    db.session.commit()
    
    # Get user and verified contacts
    user = User.query.get(user_id)
    if not user:
        return False, "User not found", 0
    
    contacts = TrustedContact.query.filter_by(
        user_id=user_id,
        is_verified=True
    ).all()
    
    if not notify_contacts:
        return True, "SOS cancelled as false alarm before dispatch", 0

    if not contacts:
        return True, "Safe status updated (no verified contacts to notify)", 0
    
    # Send WhatsApp safe notifications to all verified contacts
    user_full_name = user.full_name if user.full_name else "Someone"
    contacts_notified = 0
    
    from app.services.whatsapp_service import send_safe_notification
    
    # Ensure the timestamp is localized before sending the notification
    display_time, tz_label = format_datetime_for_display(datetime.utcnow(), user.country)

    for contact in contacts:
        try:
            success, sid = send_safe_notification(
                user_full_name,
                contact.phone,
                display_time,  # Localized time
                tz_label,      # Timezone label
            )
            if success:
                contacts_notified += 1
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to send safe notification to {contact.phone}: {e}")
            # Don't fail the entire request, just log and continue
    
    return True, f"Safe notification sent to {contacts_notified} contact(s)", contacts_notified

