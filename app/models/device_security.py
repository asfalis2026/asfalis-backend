from app.extensions import db
from datetime import datetime, timedelta
import uuid


class UserDeviceBinding(db.Model):
    __tablename__ = 'user_device_bindings'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, unique=True)
    device_imei = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class HandsetChangeRequest(db.Model):
    __tablename__ = 'handset_change_requests'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    old_device_imei = db.Column(db.String(64), nullable=True)
    new_device_imei = db.Column(db.String(64), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending, completed, rejected, expired
    requested_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    eligible_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.utcnow() + timedelta(hours=12))
    completed_at = db.Column(db.DateTime, nullable=True)

    @property
    def is_eligible(self):
        return datetime.utcnow() >= self.eligible_at
