
from app.extensions import db
from datetime import datetime
import uuid

class LocationHistory(db.Model):
    __tablename__ = 'location_history'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    address = db.Column(db.String(500), nullable=True)
    accuracy = db.Column(db.Float, nullable=True)
    is_sharing = db.Column(db.Boolean, default=False)
    recorded_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self):
        return {
            'latitude': self.latitude,
            'longitude': self.longitude,
            'address': self.address,
            'accuracy': self.accuracy,
            'is_sharing': self.is_sharing,
            'recorded_at': self.recorded_at.isoformat()
        }
