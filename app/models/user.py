from sqlalchemy import Column, String, Boolean, DateTime, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.database import Base


class User(Base):
    __tablename__ = 'users'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    full_name = Column(String(100), nullable=False)
    country = Column(String(100), nullable=True)
    email = Column(String(255), unique=True, nullable=True)
    phone = Column(String(20), unique=True, nullable=True)
    password_hash = Column(String(255), nullable=True)
    auth_provider = Column(Enum('phone', 'google', name='auth_provider_enum'), nullable=False)
    profile_image_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    sos_message = Column(String(500), nullable=True)
    fcm_token = Column(String(500), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    trusted_contacts = relationship('TrustedContact', backref='user', lazy=True, cascade="all, delete-orphan")
    sos_alerts = relationship('SOSAlert', backref='user', lazy=True, cascade="all, delete-orphan")
    location_history = relationship('LocationHistory', backref='user', lazy=True, cascade="all, delete-orphan")
    settings = relationship('UserSettings', uselist=False, backref='user', lazy=True, cascade="all, delete-orphan")
    devices = relationship('ConnectedDevice', backref='user', lazy=True, cascade="all, delete-orphan")
    support_tickets = relationship('SupportTicket', backref='user', lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            'id': self.id,
            'full_name': self.full_name,
            'email': self.email,
            'phone': self.phone,
            'profile_image_url': self.profile_image_url,
            'auth_provider': self.auth_provider,
            'is_active': self.is_active,
            'is_verified': self.is_verified,
            'sos_message': self.sos_message,
            'member_since': self.created_at.strftime('%B %Y')
        }
