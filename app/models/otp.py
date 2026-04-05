from sqlalchemy import Column, String, Integer, Boolean, DateTime, Enum, ForeignKey
from datetime import datetime
import uuid

from app.database import Base


class OTPRecord(Base):
    __tablename__ = 'otp_records'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    phone = Column(String(20), nullable=True)
    otp_code = Column(String(6), nullable=False)
    purpose = Column(Enum(
        'login', 'verify', 'reset_password', 'phone_verification', 'trusted_contact_verification',
        name='otp_purpose_enum'
    ), nullable=False)
    attempts = Column(Integer, default=0)
    is_used = Column(Boolean, default=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
