from sqlalchemy import Column, String, DateTime, Enum, ForeignKey
from datetime import datetime
import uuid

from app.database import Base
from app.utils.encryption import EncryptedString


class SupportTicket(Base):
    __tablename__ = 'support_tickets'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('users.id'), nullable=False)
    # ── Encrypted sensitive content ────────────────────────────────────────────
    subject = Column(EncryptedString(), nullable=False)
    message = Column(EncryptedString(), nullable=False)
    # ── Non-sensitive operational fields ──────────────────────────────────────
    status = Column(Enum('open', 'in_progress', 'resolved', name='ticket_status_enum'), default='open')
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self):
        # TypeDecorator auto-decrypts on attribute access — returns plaintext
        return {
            'ticket_id': self.id,
            'subject': self.subject,
            'message': self.message,
            'status': self.status,
            'created_at': self.created_at.isoformat()
        }
