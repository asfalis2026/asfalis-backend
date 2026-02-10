
from app.extensions import db
from datetime import datetime
import uuid

class ConnectedDevice(db.Model):
    __tablename__ = 'connected_devices'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    device_name = db.Column(db.String(100), nullable=False)
    device_mac = db.Column(db.String(17), nullable=False)
    is_connected = db.Column(db.Boolean, default=False)
    firmware_version = db.Column(db.String(20), nullable=True)
    battery_level = db.Column(db.Integer, nullable=True)
    last_seen = db.Column(db.DateTime, nullable=True)
    paired_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self):
        return {
            'device_id': self.id,
            'device_name': self.device_name,
            'is_connected': self.is_connected,
            'battery_level': self.battery_level,
            'firmware_version': self.firmware_version,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None
        }
