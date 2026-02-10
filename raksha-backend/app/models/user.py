
from app.extensions import db
from datetime import datetime
import uuid
from sqlalchemy.dialects.postgresql import UUID

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=True)
    phone = db.Column(db.String(20), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=True)
    auth_provider = db.Column(db.Enum('email', 'phone', 'google', name='auth_provider_enum'), nullable=False)
    profile_image_url = db.Column(db.String(500), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    is_verified = db.Column(db.Boolean, default=False)
    fcm_token = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    trusted_contacts = db.relationship('TrustedContact', backref='user', lazy=True)
    sos_alerts = db.relationship('SOSAlert', backref='user', lazy=True)
    location_history = db.relationship('LocationHistory', backref='user', lazy=True)
    settings = db.relationship('UserSettings', uselist=False, backref='user', lazy=True)
    devices = db.relationship('ConnectedDevice', backref='user', lazy=True)
    support_tickets = db.relationship('SupportTicket', backref='user', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'full_name': self.full_name,
            'email': self.email,
            'phone': self.phone,
            'profile_image_url': self.profile_image_url,
            'auth_provider': self.auth_provider,
            'is_active': self.is_active,
            'is_verified': self.is_verified,
            'member_since': self.created_at.strftime('%B %Y')
        }
