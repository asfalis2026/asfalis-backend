
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.support import SupportTicket
from app.extensions import db
from marshmallow import Schema, fields, ValidationError

support_bp = Blueprint('support', __name__)

class TicketSchema(Schema):
    subject = fields.Str(required=True, validate=lambda x: len(x) > 5)
    message = fields.Str(required=True, validate=lambda x: len(x) > 10)

@support_bp.route('/faq', methods=['GET'])
def get_faqs():
    # Placeholder FAQs - normally from DB
    faqs = [
        {
            "id": 1,
            "question": "How does motion detection work?",
            "answer": "Our app uses your device's accelerometer to detect unusual movements...",
            "category": "features",
            "icon": "timeline"
        },
        {
            "id": 2,
            "question": "When is SOS triggered automatically?",
            "answer": "SOS is triggered on sudden impacts, falls, or vigorous shaking...",
            "category": "sos",
            "icon": "flash_on"
        }
    ]
    query = request.args.get('search')
    if query:
        faqs = [f for f in faqs if query.lower() in f['question'].lower()]
        
    return jsonify(success=True, data=faqs), 200

@support_bp.route('/ticket', methods=['POST'])
@jwt_required()
def create_ticket():
    current_user_id = get_jwt_identity()
    schema = TicketSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify(success=False, error={"code": "VALIDATION_ERROR", "message": "Invalid request", "details": err.messages}), 400

    new_ticket = SupportTicket(
        user_id=current_user_id,
        subject=data['subject'],
        message=data['message']
    )
    db.session.add(new_ticket)
    db.session.commit()

    return jsonify(success=True, data=new_ticket.to_dict(), message="Support ticket created"), 201

@support_bp.route('/tickets', methods=['GET'])
@jwt_required()
def get_tickets():
    current_user_id = get_jwt_identity()
    tickets = SupportTicket.query.filter_by(user_id=current_user_id).order_by(SupportTicket.created_at.desc()).all()
    return jsonify(success=True, data=[t.to_dict() for t in tickets]), 200
