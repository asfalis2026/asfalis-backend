from sqlalchemy import Column, String, DateTime, Text, Enum, ForeignKey
from datetime import datetime
import uuid

from app.database import Base
from app.utils.encryption import EncryptedString, EncryptedFloat, EncryptedJSON


class SOSAlert(Base):
    __tablename__ = 'sos_alerts'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('users.id'), nullable=False)
    # ── Non-sensitive operational fields (stored in plaintext) ────────────────
    trigger_type = Column(Enum('manual', 'auto_fall', 'auto_shake', 'bracelet', 'iot_button', 'hardware_distress', name='trigger_type_enum'), nullable=False)
    status = Column(Enum('countdown', 'sent', 'cancelled', 'resolved', name='sos_status_enum'), nullable=False)
    triggered_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    sent_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolution_type = Column(String(50), nullable=True)
    trigger_reason = Column(Text, nullable=True)
    # ── Encrypted sensitive location & message data ────────────────────────────
    latitude = Column(EncryptedFloat(), nullable=False)
    longitude = Column(EncryptedFloat(), nullable=False)
    address = Column(EncryptedString(), nullable=True)
    sos_message = Column(EncryptedString(), nullable=False)
    # contacted_numbers is a list of phone numbers / names — encrypted as JSON blob
    contacted_numbers = Column(EncryptedJSON(), nullable=False)

    def to_dict(self):
        # TypeDecorator auto-decrypts on attribute access — returns plaintext
        return {
            'alert_id': self.id,
            'trigger_type': self.trigger_type,
            'address': self.address,
            'status': self.status,
            'triggered_at': self.triggered_at.isoformat(),
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'resolution_type': self.resolution_type
        }
