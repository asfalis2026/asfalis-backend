from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.database import Base
from app.utils.encryption import EncryptedString


class TrustedContact(Base):
    __tablename__ = 'trusted_contacts'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('users.id'), nullable=False)
    # ── Encrypted PII ──────────────────────────────────────────────────────────
    name = Column(EncryptedString(), nullable=False)
    phone = Column(EncryptedString(), nullable=False)
    email = Column(EncryptedString(), nullable=True)
    # ── HMAC index for phone equality lookups (duplicate-check, OTP lookup) ───
    phone_hmac = Column(String(64), nullable=True, index=True)
    # ── Non-sensitive fields ───────────────────────────────────────────────────
    relationship = Column(String(50), nullable=True)
    is_primary = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)
    verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self):
        # TypeDecorator auto-decrypts on attribute access — returns plaintext
        return {
            'id': self.id,
            'name': self.name,
            'phone': self.phone,
            'email': self.email,
            'relationship': self.relationship,
            'is_primary': self.is_primary,
            'is_verified': self.is_verified,
            'verified_at': self.verified_at.isoformat() if self.verified_at else None
        }
