"""Trusted contacts routes — converted to FastAPI.

Encryption note:
  TrustedContact.phone is stored encrypted. SQL equality lookups use
  phone_hmac (deterministic HMAC-SHA256 fingerprint) instead.
"""

import random
import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request

from app.extensions import db
from app.models.trusted_contact import TrustedContact
from app.models.otp import OTPRecord
from app.models.user import User
from app.schemas.contact_schema import ContactRequest
from app.config import Config, settings
from app.dependencies import get_current_user
from app.utils.encryption import compute_hmac
from app.services.sms_service import send_contact_verification_otp, send_contact_welcome_sms

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("")
def get_contacts(user_id: str = Depends(get_current_user)):
    contacts = TrustedContact.query.filter_by(user_id=user_id).all()
    return {"success": True, "data": [c.to_dict() for c in contacts], "count": len(contacts)}


@router.post("", status_code=200)
def add_contact(data: ContactRequest, user_id: str = Depends(get_current_user)):
    count = TrustedContact.query.filter_by(user_id=user_id).count()
    if count >= int(Config.MAX_TRUSTED_CONTACTS or 5):
        raise HTTPException(400, detail={"code": "Limit Exceeded", "message": "Max trusted contacts reached."})

    phone = data.phone
    # Duplicate check via HMAC index — phone column is encrypted, direct equality won't work
    p_hmac = compute_hmac(phone)
    if TrustedContact.query.filter_by(user_id=user_id, phone_hmac=p_hmac).first():
        raise HTTPException(400, detail={"code": "DUPLICATE", "message": "This contact already exists."})

    otp_code = str(random.randint(100000, 999999))
    expires_at = datetime.utcnow() + timedelta(seconds=Config.OTP_EXPIRY_SECONDS)

    # OTPRecord still stores phone in plaintext (OTP excluded from encryption per requirements)
    OTPRecord.query.filter_by(
        phone=phone, purpose='trusted_contact_verification', is_used=False
    ).update({'is_used': True}, synchronize_session=False)

    db.session.add(OTPRecord(
        phone=phone, otp_code=otp_code,
        purpose='trusted_contact_verification', expires_at=expires_at
    ))

    new_contact = TrustedContact(
        user_id=user_id,
        name=data.name,
        phone=phone,
        phone_hmac=p_hmac,
        email=data.email,
        relationship=data.relationship,
        is_primary=False,
        is_verified=False
    )
    db.session.add(new_contact)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise HTTPException(500, detail={"code": "INTERNAL_ERROR",
                                         "message": "Failed to initiate contact verification."})

    sms_ok, sms_detail = send_contact_verification_otp(phone, otp_code)

    resp_data = {
        "contact_id": new_contact.id,
        "phone": phone,
        "otp_sent": sms_ok,
        "expires_in_seconds": Config.OTP_EXPIRY_SECONDS
    }
    if not sms_ok:
        resp_data["otp_code"] = otp_code
        resp_data["sms_error"] = sms_detail
    elif settings.DEBUG:
        resp_data["otp_code"] = otp_code

    return {
        "success": True,
        "message": "OTP sent to contact's phone number" if sms_ok else "OTP generated (SMS failed — see otp_code)",
        "data": resp_data
    }


@router.post("/verify-otp")
def verify_contact_otp(body: dict, user_id: str = Depends(get_current_user)):
    contact_id = body.get('contact_id')
    otp_code = body.get('otp_code')
    if not contact_id or not otp_code:
        raise HTTPException(400, detail={"code": "VALIDATION_ERROR",
                                         "message": "contact_id and otp_code required."})

    contact = TrustedContact.query.filter_by(id=contact_id, user_id=user_id).first()
    if not contact:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Contact not found."})

    if contact.is_verified:
        return {"success": True, "message": "Already verified.", "data": contact.to_dict(), "already_verified": True}

    # OTPRecord.phone is stored in plaintext (OTP excluded from encryption per requirements)
    # contact.phone is decrypted transparently by the TypeDecorator
    otp_record = OTPRecord.query.filter_by(
        phone=contact.phone, purpose='trusted_contact_verification', is_used=False
    ).order_by(OTPRecord.created_at.desc()).first()

    if not otp_record:
        raise HTTPException(404, detail={"code": "OTP_NOT_FOUND", "message": "No OTP found for this contact."})
    if datetime.utcnow() > otp_record.expires_at:
        raise HTTPException(400, detail={"code": "OTP_EXPIRED", "message": "OTP has expired."})
    if otp_record.attempts >= Config.MAX_OTP_ATTEMPTS:
        raise HTTPException(400, detail={"code": "MAX_ATTEMPTS", "message": "Maximum OTP attempts exceeded."})

    otp_record.attempts += 1
    if otp_record.otp_code != otp_code:
        db.session.commit()
        raise HTTPException(400, detail={"code": "INVALID_OTP", "message": "Invalid OTP code."})

    otp_record.is_used = True
    contact.is_verified = True
    contact.verified_at = datetime.utcnow()

    if body.get('is_primary'):
        TrustedContact.query.filter_by(user_id=user_id, is_primary=True).update(
            {'is_primary': False}, synchronize_session=False)
        contact.is_primary = True

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise HTTPException(500, detail={"code": "INTERNAL_ERROR", "message": "Failed to verify contact."})

    user = db.session.get(User, user_id)
    sender_name = user.full_name if user else "Someone"
    whatsapp_from = Config.TWILIO_WHATSAPP_FROM
    whatsapp_number = whatsapp_from.replace('whatsapp:', '') if whatsapp_from else None
    sandbox_code = Config.TWILIO_SANDBOX_CODE
    if whatsapp_number and sandbox_code:
        send_contact_welcome_sms(contact.phone, sender_name, whatsapp_number, sandbox_code)

    return {"success": True, "message": "Contact verified.", "data": contact.to_dict()}


@router.post("/resend-otp")
def resend_contact_otp(body: dict, user_id: str = Depends(get_current_user)):
    contact_id = body.get('contact_id')
    if not contact_id:
        raise HTTPException(400, detail={"code": "VALIDATION_ERROR", "message": "contact_id required."})

    contact = TrustedContact.query.filter_by(id=contact_id, user_id=user_id, is_verified=False).first()
    if not contact:
        raise HTTPException(404, detail={"code": "NOT_FOUND",
                                         "message": "Pending contact not found or already verified."})

    # OTPRecord.phone is plaintext — contact.phone is decrypted by TypeDecorator
    OTPRecord.query.filter_by(
        phone=contact.phone, purpose='trusted_contact_verification', is_used=False
    ).update({'is_used': True}, synchronize_session=False)

    otp_code = str(random.randint(100000, 999999))
    expires_at = datetime.utcnow() + timedelta(seconds=Config.OTP_EXPIRY_SECONDS)
    db.session.add(OTPRecord(
        phone=contact.phone, otp_code=otp_code,
        purpose='trusted_contact_verification', expires_at=expires_at
    ))
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise HTTPException(500, detail={"code": "INTERNAL_ERROR", "message": "Failed to resend OTP."})

    sms_ok, sms_detail = send_contact_verification_otp(contact.phone, otp_code)
    resp_data = {"contact_id": contact.id, "phone": contact.phone,
                 "otp_sent": sms_ok, "expires_in_seconds": Config.OTP_EXPIRY_SECONDS}
    if not sms_ok:
        resp_data["otp_code"] = otp_code
    elif settings.DEBUG:
        resp_data["otp_code"] = otp_code

    return {"success": True,
            "message": "OTP resent." if sms_ok else "OTP generated (SMS failed — see otp_code)",
            "data": resp_data}


@router.put("/{contact_id}")
def update_contact(contact_id: str, data: ContactRequest, user_id: str = Depends(get_current_user)):
    contact = TrustedContact.query.filter_by(id=contact_id, user_id=user_id).first()
    if not contact:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Contact not found."})

    update = data.model_dump(exclude_none=True)
    if update.get('is_primary') and not contact.is_primary:
        TrustedContact.query.filter_by(user_id=user_id, is_primary=True).update(
            {'is_primary': False}, synchronize_session=False)

    for f in ('name', 'email', 'relationship', 'is_primary'):
        if f in update:
            setattr(contact, f, update[f])

    # If phone is being updated, refresh the HMAC index too
    if 'phone' in update:
        contact.phone = update['phone']
        contact.phone_hmac = compute_hmac(update['phone'])

    db.session.commit()
    return {"success": True, "data": contact.to_dict()}


@router.delete("/{contact_id}")
def delete_contact(contact_id: str, user_id: str = Depends(get_current_user)):
    contact = TrustedContact.query.filter_by(id=contact_id, user_id=user_id).first()
    if not contact:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Contact not found."})
    db.session.delete(contact)
    db.session.commit()
    return {"success": True, "message": "Contact deleted."}


@router.put("/{contact_id}/primary")
def set_primary_contact(contact_id: str, user_id: str = Depends(get_current_user)):
    contact = TrustedContact.query.filter_by(id=contact_id, user_id=user_id).first()
    if not contact:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Contact not found."})
    TrustedContact.query.filter_by(user_id=user_id, is_primary=True).update(
        {'is_primary': False}, synchronize_session=False)
    contact.is_primary = True
    db.session.commit()
    return {"success": True, "message": "Primary contact updated."}
