from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, BigInteger, ForeignKey
from datetime import datetime
import uuid

from app.database import Base


class SensorTrainingData(Base):
    __tablename__ = 'sensor_training_data'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('users.id'), nullable=False)
    timestamp = Column(BigInteger, nullable=False)  # Unix timestamp (ms)

    x = Column(Float, nullable=False)
    y = Column(Float, nullable=False)
    z = Column(Float, nullable=False)

    sensor_type = Column(String(20), nullable=False)  # 'accelerometer', 'gyroscope'

    # 0 = Safe/False Positive, 1 = Danger/True Positive
    label = Column(Integer, nullable=False)

    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'timestamp': self.timestamp,
            'x': self.x,
            'y': self.y,
            'z': self.z,
            'sensor_type': self.sensor_type,
            'label': self.label,
            'is_verified': self.is_verified,
            'created_at': self.created_at.isoformat()
        }
