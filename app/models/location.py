from sqlalchemy import Column, String, Float, Boolean, DateTime, ForeignKey
from datetime import datetime
import uuid

from app.database import Base


class LocationHistory(Base):
    __tablename__ = 'location_history'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('users.id'), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    address = Column(String(500), nullable=True)
    accuracy = Column(Float, nullable=True)
    is_sharing = Column(Boolean, default=False)
    recorded_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self):
        return {
            'latitude': self.latitude,
            'longitude': self.longitude,
            'address': self.address,
            'accuracy': self.accuracy,
            'is_sharing': self.is_sharing,
            'recorded_at': self.recorded_at.isoformat()
        }
