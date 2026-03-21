from sqlalchemy import Column, String, DateTime, ForeignKey
from datetime import datetime, timedelta
import uuid

from app.database import Base


class UserDeviceBinding(Base):
    __tablename__ = 'user_device_bindings'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('users.id'), nullable=False, unique=True)
    device_imei = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class HandsetChangeRequest(Base):
    __tablename__ = 'handset_change_requests'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('users.id'), nullable=False)
    old_device_imei = Column(String(64), nullable=True)
    new_device_imei = Column(String(64), nullable=False)
    status = Column(String(20), nullable=False, default='pending')
    requested_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    eligible_at = Column(DateTime, nullable=False, default=lambda: datetime.utcnow() + timedelta(hours=12))
    completed_at = Column(DateTime, nullable=True)

    @property
    def is_eligible(self):
        return datetime.utcnow() >= self.eligible_at
