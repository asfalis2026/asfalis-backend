
from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.trusted_contact import TrustedContact
from app.models.otp import OTPRecord
from app.extensions import db, limiter
from app.schemas.contact_schema import ContactSchema
from marshmallow import ValidationError
from app.config import Config
from app.models.user import User
from app.services.sms_service import send_contact_verification_otp, send_contact_welcome_sms
from datetime import datetime, timedelta
import random
import logging

logger = logging.getLogger(__name__)

contacts_bp = Blueprint('contacts', __name__)

@contacts_bp.route('', methods=['GET'])
@jwt_required()
def get_contacts():
    current_user_id = get_jwt_identity()
    contacts = TrustedContact.query.filter_by(user_id=current_user_id).all()
    
    return jsonify(success=True, data=[contact.to_dict() for contact in contacts], count=len(contacts)), 200

@contacts_bp.route('', methods=['POST'])
@jwt_required()
def add_contact():
    """Step 1: Initiate adding a trusted contact and send OTP for verification"""
    current_user_id = get_jwt_identity()
    
    # Check max contacts
    count = TrustedContact.query.filter_by(user_id=current_user_id).count()
    if count >= int(Config.MAX_TRUSTED_CONTACTS or 5):
        return jsonify(success=False, error={"code": "Limit Exceeded", "message": "Max trusted contacts reached"}), 400

    schema = ContactSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify(success=False, error={"code": "VALIDATION_ERROR", "message": "Invalid request", "details": err.messages}), 400

    phone = data['phone']
    
    # Check if contact with this phone already exists for the user
    existing = TrustedContact.query.filter_by(user_id=current_user_id, phone=phone).first()
    if existing:
        return jsonify(success=False, error={"code": "DUPLICATE", "message": "This contact already exists"}), 400

    # Generate OTP
    otp_code = str(random.randint(100000, 999999))
    expires_at = datetime.utcnow() + timedelta(seconds=Config.OTP_EXPIRY_SECONDS)

    # Invalidate any existing unused OTPs for this phone + purpose
    OTPRecord.query.filter_by(
        phone=phone,
        purpose='trusted_contact_verification',
        is_used=False
    ).update({'is_used': True}, synchronize_session=False)

    # Create OTP record
    otp_record = OTPRecord(
        phone=phone,
        otp_code=otp_code,
        purpose='trusted_contact_verification',
        expires_at=expires_at
    )
    db.session.add(otp_record)
    
    # Store pending contact data temporarily (we'll create a new contact after verification)
    # For now, create the contact but mark as unverified
    new_contact = TrustedContact(
        user_id=current_user_id,
        name=data['name'],
        phone=phone,
        email=data.get('email'),
        relationship=data.get('relationship'),
        is_primary=False,  # Will be set after verification
        is_verified=False
    )
    db.session.add(new_contact)
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to create pending contact for user {current_user_id}: {e}")
        return jsonify(success=False, error={"code": "INTERNAL_ERROR", "message": "Failed to initiate contact verification"}), 500

    # Send OTP via Twilio SMS
    send_status = send_contact_verification_otp(phone, otp_code)
    logger.info(f"OTP sent for trusted contact verification to {phone}: {send_status}")

    resp_data = {
        "contact_id": new_contact.id,
        "phone": phone,
        "otp_sent": send_status not in (None,),
        "sms_status": send_status,
        "expires_in_seconds": Config.OTP_EXPIRY_SECONDS
    }
    # In development mode expose the OTP so testing is possible without
    # a working Twilio account (mirrors the pattern used in auth routes).
    if current_app.debug:
        resp_data["otp_code"] = otp_code

    return jsonify(
        success=True,
        message="OTP sent to contact's phone number",
        data=resp_data
    ), 200


@contacts_bp.route('/verify-otp', methods=['POST'])
@jwt_required()
def verify_contact_otp():
    """Step 2: Verify OTP and complete adding the trusted contact"""
    current_user_id = get_jwt_identity()
    
    data = request.json
    if not data or 'contact_id' not in data or 'otp_code' not in data:
        return jsonify(success=False, error={"code": "VALIDATION_ERROR", "message": "contact_id and otp_code required"}), 400
    
    contact_id = data['contact_id']
    otp_code = data['otp_code']
    
    # First check if contact exists for this user
    contact = TrustedContact.query.filter_by(id=contact_id, user_id=current_user_id).first()
    if not contact:
        return jsonify(success=False, error={"code": "NOT_FOUND", "message": "Contact not found"}), 404
    
    # Check if already verified - return success with the verified contact
    if contact.is_verified:
        return jsonify(
            success=True, 
            message="Contact already verified",
            data=contact.to_dict(),
            already_verified=True
        ), 200
    
    # Find the OTP record
    otp_record = OTPRecord.query.filter_by(
        phone=contact.phone,
        purpose='trusted_contact_verification',
        is_used=False
    ).order_by(OTPRecord.created_at.desc()).first()
    
    if not otp_record:
        return jsonify(success=False, error={"code": "OTP_NOT_FOUND", "message": "No OTP found for this contact"}), 404
    
    # Check if OTP expired
    if datetime.utcnow() > otp_record.expires_at:
        return jsonify(success=False, error={"code": "OTP_EXPIRED", "message": "OTP has expired. Please request a new one"}), 400
    
    # Check max attempts
    if otp_record.attempts >= Config.MAX_OTP_ATTEMPTS:
        return jsonify(success=False, error={"code": "MAX_ATTEMPTS", "message": "Maximum OTP attempts exceeded"}), 400
    
    # Increment attempts
    otp_record.attempts += 1
    
    # Verify OTP
    if otp_record.otp_code != otp_code:
        db.session.commit()
        return jsonify(success=False, error={"code": "INVALID_OTP", "message": "Invalid OTP code"}), 400
    
    # Mark OTP as used
    otp_record.is_used = True
    
    # Mark contact as verified
    contact.is_verified = True
    contact.verified_at = datetime.utcnow()
    
    # If this should be primary, unset existing primary
    is_primary = data.get('is_primary', False)
    if is_primary:
        TrustedContact.query.filter_by(
            user_id=current_user_id, is_primary=True
        ).update({'is_primary': False}, synchronize_session=False)
        contact.is_primary = True
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to verify contact {contact_id}: {e}")
        return jsonify(success=False, error={"code": "INTERNAL_ERROR", "message": "Failed to verify contact"}), 500
    
    # Send welcome SMS to the contact
    user = db.session.get(User, current_user_id)
    sender_name = user.full_name if user and user.full_name else "Someone"
    
    # Use WhatsApp number for the welcome message (extract phone from "whatsapp:+14155238886" format)
    whatsapp_from = Config.TWILIO_WHATSAPP_FROM
    whatsapp_number = whatsapp_from.replace('whatsapp:', '') if whatsapp_from else None
    sandbox_code = Config.TWILIO_SANDBOX_CODE
    
    if whatsapp_number and sandbox_code:
        send_status = send_contact_welcome_sms(contact.phone, sender_name, whatsapp_number, sandbox_code)
        logger.info(f"Welcome SMS sent to verified contact {contact.phone}: {send_status}")
    
    return jsonify(
        success=True, 
        message="Contact verified and added successfully",
        data=contact.to_dict()
    ), 200


@contacts_bp.route('/resend-otp', methods=['POST'])
@jwt_required()
def resend_contact_otp():
    """Resend OTP for a pending contact verification"""
    current_user_id = get_jwt_identity()
    
    data = request.json
    if not data or 'contact_id' not in data:
        return jsonify(success=False, error={"code": "VALIDATION_ERROR", "message": "contact_id required"}), 400
    
    contact_id = data['contact_id']
    
    # Get the pending contact
    contact = TrustedContact.query.filter_by(id=contact_id, user_id=current_user_id, is_verified=False).first()
    if not contact:
        return jsonify(success=False, error={"code": "NOT_FOUND", "message": "Pending contact not found or already verified"}), 404
    
    # Mark all previous OTPs for this phone as used
    OTPRecord.query.filter_by(
        phone=contact.phone,
        purpose='trusted_contact_verification',
        is_used=False
    ).update({'is_used': True}, synchronize_session=False)
    
    # Generate new OTP
    otp_code = str(random.randint(100000, 999999))
    expires_at = datetime.utcnow() + timedelta(seconds=Config.OTP_EXPIRY_SECONDS)
    
    otp_record = OTPRecord(
        phone=contact.phone,
        otp_code=otp_code,
        purpose='trusted_contact_verification',
        expires_at=expires_at
    )
    db.session.add(otp_record)
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to create new OTP for contact {contact_id}: {e}")
        return jsonify(success=False, error={"code": "INTERNAL_ERROR", "message": "Failed to resend OTP"}), 500
    
    # Send OTP via Twilio SMS
    send_status = send_contact_verification_otp(contact.phone, otp_code)
    logger.info(f"OTP resent for trusted contact {contact.phone}: {send_status}")

    resp_data = {
        "contact_id": contact.id,
        "phone": contact.phone,
        "sms_status": send_status,
        "expires_in_seconds": Config.OTP_EXPIRY_SECONDS
    }
    # In development mode expose the OTP so testing is possible without
    # a working Twilio account (mirrors the pattern used in auth routes).
    if current_app.debug:
        resp_data["otp_code"] = otp_code

    return jsonify(
        success=True,
        message="OTP resent successfully",
        data=resp_data
    ), 200

@contacts_bp.route('/<contact_id>', methods=['PUT'])
@jwt_required()
def update_contact(contact_id):
    current_user_id = get_jwt_identity()
    contact = TrustedContact.query.filter_by(id=contact_id, user_id=current_user_id).first()
    
    if not contact:
        return jsonify(success=False, error={"code": "NOT_FOUND", "message": "Contact not found"}), 404

    schema = ContactSchema(partial=True) # Allow partial updates
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify(success=False, error={"code": "VALIDATION_ERROR", "message": "Invalid request", "details": err.messages}), 400

    if data.get('is_primary') and not contact.is_primary:
        TrustedContact.query.filter_by(
            user_id=current_user_id, is_primary=True
        ).update({'is_primary': False}, synchronize_session=False)

    if 'name' in data: contact.name = data['name']
    if 'phone' in data: contact.phone = data['phone']
    if 'email' in data: contact.email = data['email']
    if 'relationship' in data: contact.relationship = data['relationship']
    if 'is_primary' in data: contact.is_primary = data['is_primary']

    db.session.commit()
    return jsonify(success=True, data=contact.to_dict()), 200

@contacts_bp.route('/<contact_id>', methods=['DELETE'])
@jwt_required()
def delete_contact(contact_id):
    current_user_id = get_jwt_identity()
    contact = TrustedContact.query.filter_by(id=contact_id, user_id=current_user_id).first()
    
    if not contact:
        return jsonify(success=False, error={"code": "NOT_FOUND", "message": "Contact not found"}), 404

    db.session.delete(contact)
    db.session.commit()
    return jsonify(success=True, message="Contact deleted"), 200

@contacts_bp.route('/<contact_id>/primary', methods=['PUT'])
@jwt_required()
def set_primary_contact(contact_id):
    current_user_id = get_jwt_identity()
    contact = TrustedContact.query.filter_by(id=contact_id, user_id=current_user_id).first()
    
    if not contact:
        return jsonify(success=False, error={"code": "NOT_FOUND", "message": "Contact not found"}), 404

    TrustedContact.query.filter_by(
        user_id=current_user_id, is_primary=True
    ).update({'is_primary': False}, synchronize_session=False)
    contact.is_primary = True
    db.session.commit()

    return jsonify(success=True, message="Primary contact updated"), 200
