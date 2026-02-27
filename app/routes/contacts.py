
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.trusted_contact import TrustedContact
from app.extensions import db, limiter
from app.schemas.contact_schema import ContactSchema
from marshmallow import ValidationError
from app.config import Config
from app.models.user import User

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

    # If new contact is primary, unset existing primary
    if data.get('is_primary'):
        TrustedContact.query.filter_by(user_id=current_user_id, is_primary=True).update({'is_primary': False})

    new_contact = TrustedContact(
        user_id=current_user_id,
        name=data['name'],
        phone=data['phone'],
        email=data.get('email'),
        relationship=data.get('relationship'),
        is_primary=data.get('is_primary', False)
    )
    
    db.session.add(new_contact)
    db.session.commit()

    # Build WhatsApp join info so the Android app can send an invite
    # via native SMS / share intent (no server-side email needed).
    whatsapp_join_info = None
    twilio_number = Config.TWILIO_PHONE_NUMBER
    sandbox_code = Config.TWILIO_SANDBOX_CODE
    if twilio_number and sandbox_code:
        clean_number = twilio_number.replace('+', '').replace('-', '').replace(' ', '')
        encoded_code = sandbox_code.replace(' ', '%20')
        whatsapp_join_info = {
            "twilio_number": twilio_number,
            "sandbox_code": sandbox_code,
            "whatsapp_link": f"https://wa.me/{clean_number}?text={encoded_code}"
        }

    user = User.query.get(current_user_id)
    response_data = new_contact.to_dict()
    response_data["whatsapp_join_info"] = whatsapp_join_info
    response_data["invite_message"] = (
        f"{user.full_name if user else 'Someone'} added you as a trusted contact "
        f"in Asfalis, a personal safety app. You will receive emergency alerts "
        f"with their location if they trigger an SOS."
    )

    return jsonify(success=True, data=response_data), 201

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
         TrustedContact.query.filter_by(user_id=current_user_id, is_primary=True).update({'is_primary': False})

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

    TrustedContact.query.filter_by(user_id=current_user_id, is_primary=True).update({'is_primary': False})
    contact.is_primary = True
    db.session.commit()

    return jsonify(success=True, message="Primary contact updated"), 200
