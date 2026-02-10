
import random
import string
from datetime import datetime, timedelta
from app.extensions import db
from app.models.otp import OTPRecord
from app.config import Config

def generate_otp(length=4):
    """Generate a numeric OTP of given length."""
    return ''.join(random.choices(string.digits, k=length))

def store_otp(phone, otp_code, purpose):
    """Store OTP in database."""
    # Invalidate existing OTPs for this phone and purpose
    OTPRecord.query.filter_by(phone=phone, purpose=purpose, is_used=False).update({'is_used': True})
    
    expires_at = datetime.utcnow() + timedelta(seconds=int(Config.OTP_EXPIRY_SECONDS or 300))
    
    otp_record = OTPRecord(
        phone=phone,
        otp_code=otp_code, # Should hash this in production
        purpose=purpose,
        expires_at=expires_at
    )
    db.session.add(otp_record)
    db.session.commit()
    return otp_record

def verify_otp(phone, otp_code, purpose):
    """Verify OTP."""
    otp_record = OTPRecord.query.filter_by(
        phone=phone, 
        purpose=purpose, 
        is_used=False
    ).order_by(OTPRecord.created_at.desc()).first()

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
