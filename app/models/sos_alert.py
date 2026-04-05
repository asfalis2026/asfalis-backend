from sqlalchemy import Column, String, Float, DateTime, Text, JSON, Enum, ForeignKey
from datetime import datetime
import uuid

from app.database import Base


class SOSAlert(Base):
    __tablename__ = 'sos_alerts'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('users.id'), nullable=False)
    trigger_type = Column(Enum('manual', 'auto_fall', 'auto_shake', 'bracelet', 'iot_button', name='trigger_type_enum'), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    address = Column(String(500), nullable=True)
    status = Column(Enum('countdown', 'sent', 'cancelled', 'resolved', name='sos_status_enum'), nullable=False)
    sos_message = Column(Text, nullable=False)
    contacted_numbers = Column(JSON, nullable=False)
    triggered_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    sent_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolution_type = Column(String(50), nullable=True)
    trigger_reason = Column(Text, nullable=True)

    def to_dict(self):
        return {
            'alert_id': self.id,
            'trigger_type': self.trigger_type,
            'address': self.address,
            'status': self.status,
            'triggered_at': self.triggered_at.isoformat(),
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'resolution_type': self.resolution_type
        }
