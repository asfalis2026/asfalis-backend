from sqlalchemy import Column, String, Boolean, DateTime, Enum, Integer
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
import uuid

from app.database import Base
from app.utils.encryption import EncryptedString


class User(Base):
    __tablename__ = 'users'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # ── Encrypted PII ──────────────────────────────────────────────────────────
    full_name = Column(EncryptedString(), nullable=False)
    email = Column(EncryptedString(), nullable=True)
    phone = Column(EncryptedString(), nullable=True)
    sos_message = Column(EncryptedString(), nullable=True)
    fcm_token = Column(EncryptedString(), nullable=True)
    profile_image_url = Column(EncryptedString(), nullable=True)
    # ── HMAC index columns — enable equality lookups on encrypted fields ────────
    # Use phone_hmac / email_hmac in filter_by() instead of the plaintext columns.
    phone_hmac = Column(String(64), unique=True, nullable=True, index=True)
    email_hmac = Column(String(64), unique=True, nullable=True, index=True)
    # ── Non-sensitive fields — stored in plaintext ─────────────────────────────
    country = Column(String(100), nullable=True)
    password_hash = Column(String(255), nullable=True)
    auth_provider = Column(Enum('phone', 'google', name='auth_provider_enum'), nullable=False)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    # ── Account security ───────────────────────────────────────────────────────
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    trusted_contacts = relationship('TrustedContact', backref='user', lazy=True, cascade="all, delete-orphan")
    sos_alerts = relationship('SOSAlert', backref='user', lazy=True, cascade="all, delete-orphan")
    location_history = relationship('LocationHistory', backref='user', lazy=True, cascade="all, delete-orphan")
    settings = relationship('UserSettings', uselist=False, backref='user', lazy=True, cascade="all, delete-orphan")
    devices = relationship('ConnectedDevice', backref='user', lazy=True, cascade="all, delete-orphan")
    support_tickets = relationship('SupportTicket', backref='user', lazy=True, cascade="all, delete-orphan")
    device_bindings = relationship('UserDeviceBinding', uselist=False, backref='user', lazy=True, cascade="all, delete-orphan")
    handset_change_requests = relationship('HandsetChangeRequest', backref='user', lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        # TypeDecorator auto-decrypts on attribute access — returns plaintext
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

    def is_locked(self) -> bool:
        """Check if account is currently locked due to failed attempts."""
        if self.locked_until and self.locked_until > datetime.utcnow():
            return True
        return False

    def get_lockout_remaining_seconds(self) -> int:
        """Get remaining seconds until account is unlocked."""
        if not self.locked_until:
            return 0
        remaining = self.locked_until - datetime.utcnow()
        return max(0, int(remaining.total_seconds()))

    def record_failed_login(self, max_attempts: int = 5, lockout_minutes: int = 30):
        """Record a failed login attempt and lock account if threshold exceeded."""
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= max_attempts:
            self.locked_until = datetime.utcnow() + timedelta(minutes=lockout_minutes)

    def reset_failed_logins(self):
        """Reset failed login counter after successful login."""
        self.failed_login_attempts = 0
        self.locked_until = None
