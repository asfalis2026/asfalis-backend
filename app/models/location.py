from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from datetime import datetime
import uuid

from app.database import Base
from app.utils.encryption import EncryptedString, EncryptedFloat


class LocationHistory(Base):
    __tablename__ = 'location_history'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('users.id'), nullable=False)
    # ── Encrypted location data ────────────────────────────────────────────────
    latitude = Column(EncryptedFloat(), nullable=False)
    longitude = Column(EncryptedFloat(), nullable=False)
    address = Column(EncryptedString(), nullable=True)
    # ── Non-sensitive operational fields ──────────────────────────────────────
    accuracy = Column(EncryptedFloat(), nullable=True)
    is_sharing = Column(Boolean, default=False)
    recorded_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self):
        # TypeDecorator auto-decrypts on attribute access — returns plaintext floats/strings
        return {
            'latitude': self.latitude,
            'longitude': self.longitude,
            'address': self.address,
            'accuracy': self.accuracy,
            'is_sharing': self.is_sharing,
            'recorded_at': self.recorded_at.isoformat()
        }
