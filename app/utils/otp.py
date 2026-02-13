
import random
import string
from datetime import datetime, timedelta
from app.extensions import db
from app.models.otp import OTPRecord
from app.config import Config

def generate_otp(length=6):
    """Generate a numeric OTP of given length."""
    return ''.join(random.choices(string.digits, k=length))

def store_otp(phone=None, email=None, otp_code=None, purpose=None):
    """Store OTP in database."""
    if not phone and not email:
        raise ValueError("Either phone or email must be provided")

    # Invalidate existing OTPs
    query_filter = {
        'purpose': purpose,
        'is_used': False
    }
    if phone:
        query_filter['phone'] = phone
    if email:
        query_filter['email'] = email
        
    OTPRecord.query.filter_by(**query_filter).update({'is_used': True})
    
    expires_at = datetime.utcnow() + timedelta(seconds=int(Config.OTP_EXPIRY_SECONDS or 300))
    
    otp_record = OTPRecord(
        phone=phone,
        email=email,
        otp_code=otp_code,
        purpose=purpose,
        expires_at=expires_at
    )
    db.session.add(otp_record)
    db.session.commit()
    return otp_record

def verify_otp(phone=None, email=None, otp_code=None, purpose=None):
    """Verify OTP."""
    if not phone and not email:
        return False, "Identifier required"

    query_filter = {
        'purpose': purpose,
        'is_used': False
    }
    if phone:
        query_filter['phone'] = phone
    if email:
        query_filter['email'] = email

    otp_record = OTPRecord.query.filter_by(**query_filter).order_by(OTPRecord.created_at.desc()).first()

    if not otp_record:
        return False, "OTP not found or expired"

    if otp_record.expires_at < datetime.utcnow():
        return False, "OTP expired"

    if otp_record.attempts >= int(Config.MAX_OTP_ATTEMPTS or 5):
         return False, "Too many attempts"

    if otp_record.otp_code != otp_code:
        otp_record.attempts += 1
        db.session.commit()
        return False, "Invalid OTP"

    otp_record.is_used = True
    db.session.commit()
    return True, "OTP verified"
