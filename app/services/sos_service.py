from app.config import settings
from app.extensions import db
from app.models.sos_alert import SOSAlert
from app.models.trusted_contact import TrustedContact
from app.models.user import User
from app.services.fcm_service import send_push_notification
from app.utils.timezone_utils import format_datetime_for_display
from datetime import datetime
import logging

COUNTDOWN_SECONDS = 10          # The live countdown window the app displays (seconds)
COUNTDOWN_EXPIRY_SECONDS = 60  # Backend stale-cleanup guard — cancel if still 'countdown' after 60s


def _get_configured_cooldown():
    """Fetch SOS cooldown from settings."""
    value = getattr(settings, 'SOS_COOLDOWN_SECONDS', None)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

def trigger_sos(user_id, lat, lng, trigger_type='manual', trigger_prefix=None, trigger_reason=None):
    # Auto-SOS (sensor-based): 10-minute cooldown via _sos_cooldown.
    # Manual SOS: 20-second double-tap guard via _manual_sos_cooldown.
    # IoT button: NO backend cooldown — IotSosTracker on Android owns the
    # 10-minute hardware cooldown entirely.  Applying a second in-process
    # cooldown here would block re-triggering after a cancel and make the
    # IoT device unresponsive for up to 20 seconds.
    # The two cooldown stores are otherwise independent — a manual SOS never
    # blocks an auto-SOS and an auto-SOS never blocks a manual one.
    is_auto = trigger_type.startswith('auto')
    is_iot  = trigger_type == 'iot_button'

    if is_auto:
        from app.services.protection_service import (
            _is_on_cooldown, _mark_sos_triggered
        )
        on_cooldown, secs_left = _is_on_cooldown(user_id)
        mark_triggered = lambda: _mark_sos_triggered(user_id)
    elif is_iot:
        # Hardware cooldown is enforced by IotSosTracker (Android side).
        # Backend applies no additional rate-limit for iot_button.
        on_cooldown, secs_left = False, 0
        mark_triggered = lambda: None  # no-op
    else:
        from app.services.protection_service import (
            _is_manual_on_cooldown, _mark_manual_sos_triggered
        )
        on_cooldown, secs_left = _is_manual_on_cooldown(user_id)
        mark_triggered = lambda: _mark_manual_sos_triggered(user_id)

    if on_cooldown:
        existing = SOSAlert.query.filter_by(user_id=user_id, status='countdown').first()
        if existing:
            return existing, f"SOS on cooldown — please wait {secs_left}s before triggering again.", COUNTDOWN_SECONDS
        return None, f"SOS on cooldown — please wait {secs_left}s before triggering again.", COUNTDOWN_SECONDS

    user = db.session.get(User, user_id)
    if not user:
        return None, "User not found", COUNTDOWN_SECONDS

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
            return existing_alert, "Alert already in countdown", COUNTDOWN_SECONDS

    # Prioritize the new sos_message on User model, fallback to Settings or Default
    start_message = "Emergency!"
    if user.sos_message:
        start_message = user.sos_message
    elif user.settings and user.settings.sos_message:
        start_message = user.settings.sos_message

    # Auto-SOS paths pass a trigger_prefix (reason + confidence) that is
    # prepended to the user's normal SOS message.  This surfaces in the
    # WhatsApp notification so contacts and the user know exactly what
    # triggered the alert.
    sos_message = f"{trigger_prefix}\n\n{start_message}" if trigger_prefix else start_message

    new_alert = SOSAlert(
        user_id=user_id,
        trigger_type=trigger_type,
        trigger_reason=trigger_reason,
        latitude=lat,
        longitude=lng,
        status='countdown',
        sos_message=sos_message,
        contacted_numbers=[]
    )
    db.session.add(new_alert)
    db.session.commit()

    # Mark cooldown for this user (auto or manual store depending on trigger_type)
    mark_triggered()

    # ── Server-side auto-dispatch guard ─────────────────────────────────────
    # The mobile app should call POST /sos/send-now once the countdown elapses.
    # This background thread is a safety net: if the app is killed, crashes, or
    # (during Postman testing) never calls /send-now, the backend will auto-
    # dispatch after COUNTDOWN_SECONDS + a small grace period.
    alert_id_snapshot = new_alert.id

    def _auto_dispatch_after_countdown(aid, delay):
        import time
        time.sleep(delay)
        try:
            from app.database import ScopedSession
            session = ScopedSession()
            alert_obj = session.get(SOSAlert, aid)
            if alert_obj and alert_obj.status == 'countdown':
                logger = logging.getLogger(__name__)
                logger.info(f"[auto-dispatch] Alert {aid} still in countdown after {delay}s — dispatching now.")
                # dispatch_sos operates on ScopedSession internally; remove our
                # local reference first so it gets a fresh thread-local session.
                ScopedSession.remove()
                dispatch_sos(aid)
            else:
                ScopedSession.remove()
        except Exception as exc:
            logging.getLogger(__name__).error(
                f"[auto-dispatch] Failed for alert {aid}: {exc}"
            )
            try:
                from app.database import ScopedSession as _S
                _S.remove()
            except Exception:
                pass

    import threading
    grace = COUNTDOWN_SECONDS + 2   # 2-second grace for network latency
    t = threading.Thread(
        target=_auto_dispatch_after_countdown,
        args=(alert_id_snapshot, grace),
        daemon=True,
        name=f"sos-auto-{alert_id_snapshot[:8]}",
    )
    t.start()

    return new_alert, "SOS countdown started", COUNTDOWN_SECONDS

def dispatch_sos(alert_id, user_id=None):
    alert = db.session.get(SOSAlert, alert_id)
    if not alert:
        return False, "Alert not found", []

    if user_id and alert.user_id != user_id:
        return False, "Unauthorized: This alert does not belong to you", []

    if alert.status in ['resolved', 'cancelled']:
        return False, "Alert already resolved/cancelled", []

    if alert.status == 'sent':
        return True, "SOS already dispatched", []

    if alert.status != 'countdown':
        return False, f"Alert cannot be dispatched from state: {alert.status}", []

    user = db.session.get(User, alert.user_id)
    contacts = TrustedContact.query.filter_by(user_id=user.id).all()

    # Warn if none are app-verified (contact joined Twilio sandbox ≠ app OTP verified)
    unverified = [c for c in contacts if not c.is_verified]
    if unverified:
        logger = logging.getLogger(__name__)
        logger.warning(
            f"{len(unverified)} contact(s) for user {user.id} are not app-verified "
            "but will still receive the SOS alert."
        )

    alert.status = 'sent'
    alert.sent_at = datetime.utcnow()

    # Generate Google Maps link and structured message body
    maps_link = (
        f"https://maps.google.com/?q={alert.latitude},{alert.longitude}"
        if (alert.latitude and alert.longitude) else None
    )
    from app.services.whatsapp_service import send_whatsapp_sync, _build_sos_body
    full_message = _build_sos_body(
        user_name=user.full_name or "Someone",
        trigger_type=alert.trigger_type,
        trigger_reason=alert.trigger_reason,
        maps_link=maps_link,
    )

    contacted = []
    delivery_report = []  # per-contact Twilio delivery status

    for contact in contacts:
        contacted.append(contact.phone)
        result = send_whatsapp_sync(contact.phone, full_message)
        delivery_report.append({
            "phone":      contact.phone,
            "success":    result["success"],
            "status":     result["status"],
            "error_code": result["error_code"],
            "error_msg":  result["error_msg"],
        })
        if not result["success"]:
            _log = logging.getLogger(__name__)
            _log.warning(
                f"SOS delivery failed for {contact.phone} "
                f"[{result['status']}] code={result['error_code']}: {result['error_msg']}"
            )

    alert.contacted_numbers = contacted
    db.session.commit()

    failed = [r for r in delivery_report if not r["success"]]
    sandbox_issues = [r for r in failed if r["status"] in ("not_in_sandbox", "not_opted_in")]

    summary = "SOS Dispatched via WhatsApp"
    if sandbox_issues:
        summary += (
            f" ({len(sandbox_issues)} contact(s) not in Twilio sandbox — "
            "they must text the sandbox join keyword first)"
        )
    elif failed:
        summary += f" ({len(failed)} delivery failure(s) — check logs)"

    return True, summary, delivery_report

def cancel_sos(alert_id, user_id=None):
    alert = db.session.get(SOSAlert, alert_id)
    if not alert:
        return False, "Alert not found"

    if user_id and alert.user_id != user_id:
        return False, "Unauthorized: This alert does not belong to you"

    if alert.status in ('cancelled', 'resolved'):
        return False, f"This alert has already been resolved (status: {alert.status})"

    trigger_type = alert.trigger_type or ''

    alert.status = 'cancelled'
    alert.resolved_at = datetime.utcnow()
    alert.resolution_type = 'cancelled'
    db.session.commit()

    # ── Flow 2: Auto ML Trigger ──────────────────────────────────────────────
    # Cancel Received → Mark window as SAFE → Store in DB → Improve ML dataset
    if trigger_type.startswith('auto') and user_id:
        try:
            from app.services.protection_service import submit_sos_feedback
            submit_sos_feedback(user_id, alert.id, is_false_alarm=True)
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to auto-submit feedback for cancelled auto-sos: {e}")

    # ── Flow 3: Hardware Auto Distress ───────────────────────────────────────
    # Cancel Received → Mark Safe → No escalation (app handles reconnect logic)
    # We still store an ML safe-window for better future predictions.
    elif trigger_type == 'hardware_distress' and user_id:
        try:
            from app.services.protection_service import submit_sos_feedback
            submit_sos_feedback(user_id, alert.id, is_false_alarm=True)
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to submit feedback for cancelled hardware_distress: {e}")

    # ── Flow 1: Manual SOS / IoT button ─────────────────────────────────────
    # Cancel Received → Mark Safe → Send 'I am Safe' via WhatsApp
    elif trigger_type in ['manual', 'iot_button']:
        user = db.session.get(User, alert.user_id)
        if user:
            contacts = TrustedContact.query.filter_by(user_id=alert.user_id).all()
            if contacts:
                from app.services.whatsapp_service import send_safe_notification
                from app.utils.timezone_utils import format_datetime_for_display
                display_time, tz_label = format_datetime_for_display(datetime.utcnow(), user.country)
                user_full_name = user.full_name if user.full_name else "Someone"
                for contact in contacts:
                    try:
                        send_safe_notification(user_full_name, contact.phone, display_time, tz_label)
                    except Exception as e:
                        logger = logging.getLogger(__name__)
                        logger.error(f"Failed to send safe notification to {contact.phone}: {e}")

    # Clear the manual cooldown so the user can re-trigger immediately after cancel.
    # This is a no-op when user_id is None.
    if user_id:
        try:
            from app.services.protection_service import _clear_manual_cooldown
            _clear_manual_cooldown(user_id)
        except Exception:
            pass  # Never let a cooldown-clear failure abort a successful cancel

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
    alert = db.session.get(SOSAlert, alert_id)
    
    # Validation checks
    if not alert:
        return False, "Alert not found", 0
    
    # Verify alert belongs to the authenticated user
    if alert.user_id != user_id:
        return False, "Unauthorized: This alert does not belong to you", 0
    
    # Check if alert is already resolved
    if alert.status in ['cancelled', 'resolved']:
        return False, f"This alert has already been resolved (status: {alert.status})", 0
    
    # Idempotency guard: user already marked safe after a dispatched SOS —
    # return success so the app doesn't show an error on a double-tap.
    if alert.resolution_type == 'user_marked_safe':
        return True, "Alert already marked as safe", 0
    
    # State transition rules:
    # - countdown -> cancelled, resolution_type='false_alarm'
    #   (SOS was never dispatched; no contacts to notify)
    # - sent -> cancelled, resolution_type='user_marked_safe'
    #   (SOS was dispatched; safe message must go out to contacts)
    notify_contacts = alert.status == 'sent'
    resolution = 'user_marked_safe' if notify_contacts else 'false_alarm'

    alert.status = 'cancelled'
    alert.resolved_at = datetime.utcnow()
    alert.resolution_type = resolution
    db.session.commit()
    
    # Get user and verified contacts
    user = db.session.get(User, user_id)
    if not user:
        return False, "User not found", 0
    
    contacts = TrustedContact.query.filter_by(
        user_id=user_id
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

