
from app.extensions import db
from datetime import datetime
import uuid

class UserSettings(db.Model):
    __tablename__ = 'user_settings'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), unique=True, nullable=False)
    emergency_number = db.Column(db.String(20), nullable=False, default='911')
    sos_message = db.Column(db.Text, nullable=False, default="Emergency! I need help. This is an automated SOS alert from Women Safety app. My live location is attached.")
    shake_sensitivity = db.Column(db.Enum('low', 'medium', 'high', name='sensitivity_enum'), default='medium')
    battery_optimization = db.Column(db.Boolean, default=True)
    haptic_feedback = db.Column(db.Boolean, default=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'emergency_number': self.emergency_number,
            'sos_message': self.sos_message,
            'shake_sensitivity': self.shake_sensitivity,
            'battery_optimization': self.battery_optimization,
            'haptic_feedback': self.haptic_feedback
        }
