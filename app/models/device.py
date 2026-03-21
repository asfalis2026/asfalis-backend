from sqlalchemy import Column, String, Boolean, Integer, DateTime, ForeignKey
from datetime import datetime
import uuid

from app.database import Base


class ConnectedDevice(Base):
    __tablename__ = 'connected_devices'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('users.id'), nullable=False)
    device_name = Column(String(100), nullable=False)
    device_mac = Column(String(17), nullable=False)
    is_connected = Column(Boolean, default=False)
    firmware_version = Column(String(20), nullable=True)
    battery_level = Column(Integer, nullable=True)
    last_seen = Column(DateTime, nullable=True)
    paired_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_button_press_at = Column(DateTime, nullable=True)

    def to_dict(self):
        return {
            'device_id': self.id,
            'device_name': self.device_name,
            'device_mac': self.device_mac,
            'is_connected': self.is_connected,
            'battery_level': self.battery_level,
            'firmware_version': self.firmware_version,
            'signal_strength': None,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None,
            'last_button_press_at': self.last_button_press_at.isoformat() if self.last_button_press_at else None
        }
