
from flask_mail import Message
from app.extensions import mail
from flask import current_app
import logging

logger = logging.getLogger(__name__)

def send_otp_email(to_email, otp_code):
    """
    Sends an OTP to the specified email address.
    """
    try:
        subject = "Your Verification Code - Asfalis"
        sender = current_app.config.get('MAIL_USERNAME')
        if not sender:
            logger.warning("MAIL_USERNAME not set. Email sending will fail.")
        
        msg = Message(subject, sender=sender, recipients=[to_email])
        msg.body = f"Your Verification Code is: {otp_code}\n\nThis code is valid for 5 minutes.\nDo not share this code with anyone."
        
        mail.send(msg)
        logger.info(f"OTP sent to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send OTP email to {to_email}: {str(e)}")
        return False
