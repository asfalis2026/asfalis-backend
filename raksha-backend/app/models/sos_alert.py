
from app.extensions import db
from datetime import datetime
import uuid

class SOSAlert(db.Model):
    __tablename__ = 'sos_alerts'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    trigger_type = db.Column(db.Enum('manual', 'auto_fall', 'auto_shake', 'bracelet', name='trigger_type_enum'), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    address = db.Column(db.String(500), nullable=True)
    status = db.Column(db.Enum('countdown', 'sent', 'cancelled', 'resolved', name='sos_status_enum'), nullable=False)
    sos_message = db.Column(db.Text, nullable=False)
    contacted_numbers = db.Column(db.JSON, nullable=False)
    triggered_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    sent_at = db.Column(db.DateTime, nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            'alert_id': self.id,
            'trigger_type': self.trigger_type,
            'address': self.address,
            'status': self.status,
            'triggered_at': self.triggered_at.isoformat(),
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None
        }
