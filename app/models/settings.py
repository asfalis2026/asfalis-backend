from sqlalchemy import Column, String, Boolean, DateTime, Enum, ForeignKey
from datetime import datetime
import uuid

from app.database import Base
from app.utils.encryption import EncryptedString


class UserSettings(Base):
    __tablename__ = 'user_settings'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('users.id'), unique=True, nullable=False)
    # ── Encrypted sensitive fields ─────────────────────────────────────────────
    emergency_number = Column(EncryptedString(), nullable=False)
    sos_message = Column(EncryptedString(), nullable=False)
    # ── Non-sensitive preference flags (stored in plaintext) ──────────────────
    shake_sensitivity = Column(Enum('low', 'medium', 'high', name='sensitivity_enum'), default='medium')
    battery_optimization = Column(Boolean, default=True)
    haptic_feedback = Column(Boolean, default=True)
    auto_sos_enabled = Column(Boolean, default=False, nullable=False)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        # TypeDecorator auto-decrypts on attribute access — returns plaintext
        return {
            'emergency_number': self.emergency_number,
            'sos_message': self.sos_message,
            'shake_sensitivity': self.shake_sensitivity,
            'battery_optimization': self.battery_optimization,
            'haptic_feedback': self.haptic_feedback,
            'auto_sos_enabled': self.auto_sos_enabled
        }
