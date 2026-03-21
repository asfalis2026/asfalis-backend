"""Support routes — converted to FastAPI."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from app.extensions import db
from app.models.support import SupportTicket
from app.dependencies import get_current_user

router = APIRouter()


class TicketRequest(BaseModel):
    subject: str = Field(..., min_length=6)
    message: str = Field(..., min_length=11)


@router.get("/faq")
def get_faqs(search: Optional[str] = None):
    faqs = [
        {"id": 1, "question": "How does motion detection work?",
         "answer": "Our app uses your device's accelerometer to detect unusual movements...",
         "category": "features", "icon": "timeline"},
        {"id": 2, "question": "When is SOS triggered automatically?",
         "answer": "SOS is triggered on sudden impacts, falls, or vigorous shaking...",
         "category": "sos", "icon": "flash_on"},
    ]
    if search:
        faqs = [f for f in faqs if search.lower() in f['question'].lower()]
    return {"success": True, "data": faqs}


@router.post("/ticket", status_code=201)
def create_ticket(data: TicketRequest, user_id: str = Depends(get_current_user)):
    ticket = SupportTicket(user_id=user_id, subject=data.subject, message=data.message)
    db.session.add(ticket)
    db.session.commit()
    return {"success": True, "data": ticket.to_dict(), "message": "Support ticket created."}


@router.get("/tickets")
def get_tickets(user_id: str = Depends(get_current_user)):
    tickets = SupportTicket.query.filter_by(user_id=user_id).order_by(SupportTicket.created_at.desc()).all()
    return {"success": True, "data": [t.to_dict() for t in tickets]}
