from sqlalchemy import Column, String, Boolean, Float, DateTime, LargeBinary
from datetime import datetime
import uuid

from app.database import Base


class MLModel(Base):
    __tablename__ = 'ml_models'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    version = Column(String(20), nullable=False)
    is_active = Column(Boolean, default=False)
    data = Column(LargeBinary, nullable=False)  # Pickled model bytes
    accuracy = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'version': self.version,
            'is_active': self.is_active,
            'accuracy': self.accuracy,
            'created_at': self.created_at.isoformat()
        }
