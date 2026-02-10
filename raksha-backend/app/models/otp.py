
from app.extensions import db
from datetime import datetime
import uuid

class OTPRecord(db.Model):
    __tablename__ = 'otp_records'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    phone = db.Column(db.String(20), nullable=False)
    otp_code = db.Column(db.String(6), nullable=False) # Hashed in production usually, keeping simple for now or hashed
    purpose = db.Column(db.Enum('login', 'verify', 'reset_password', name='otp_purpose_enum'), nullable=False)
    attempts = db.Column(db.Integer, default=0)
    is_used = db.Column(db.Boolean, default=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
