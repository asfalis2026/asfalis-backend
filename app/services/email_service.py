
from flask_mail import Message
from app.extensions import mail
from flask import current_app
import logging
import threading

logger = logging.getLogger(__name__)


def _send_email_thread(app, subject, recipient, html_body, sender):
    """Send email via Flask-Mail in a background thread."""
    with app.app_context():
        try:
            msg = Message(subject, sender=sender, recipients=[recipient])
            msg.html = html_body
            mail.send(msg)
            logger.info(f"Email sent to {recipient}")
        except Exception as e:
            logger.error(f"Failed to send email to {recipient}: {str(e)}")


def _dispatch_email(subject, to_email, html_body):
    """Dispatch an email in a background thread via Flask-Mail.

    Uses MAIL_SERVER / MAIL_USERNAME / MAIL_PASSWORD from config.
    Point MAIL_SERVER at smtp.sendgrid.net and set MAIL_USERNAME=apikey,
    MAIL_PASSWORD=<SendGrid API key> for production on Render.
    """
    sender = current_app.config.get('MAIL_USERNAME')
    mail_password = current_app.config.get('MAIL_PASSWORD')

    if not sender or not mail_password:
        logger.warning(
            "Email not sent — MAIL_USERNAME or MAIL_PASSWORD is not set. "
            "Set MAIL_SERVER=smtp.sendgrid.net, MAIL_USERNAME=apikey, "
            "MAIL_PASSWORD=<SendGrid API key> in your environment variables."
        )
        return False

    app = current_app._get_current_object()
    t = threading.Thread(
        target=_send_email_thread,
        args=(app, subject, to_email, html_body, sender),
        daemon=True
    )
    t.start()
    return True


def send_otp_email(to_email, otp_code):
    """Sends an OTP to the specified email address."""
    try:
        subject = "Your Verification Code - Asfalis"
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background-color: #f4f4f4; margin: 0; padding: 0; }}
                .container {{ max-width: 600px; margin: 20px auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
                .header {{ background-color: #4CAF50; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 30px; color: #333333; line-height: 1.6; text-align: center; }}
                .otp-code {{ font-size: 32px; font-weight: bold; color: #4CAF50; letter-spacing: 5px; margin: 20px 0; background-color: #f0f8f0; padding: 10px; display: inline-block; border-radius: 4px; }}
                .footer {{ background-color: #eeeeee; color: #777777; padding: 15px; text-align: center; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header"><h1>Verification Code</h1></div>
                <div class="content">
                    <p>Hello,</p>
                    <p>Use the following code to verify your email address for <strong>Asfalis</strong>.</p>
                    <div class="otp-code">{otp_code}</div>
                    <p>This code is valid for <strong>5 minutes</strong>.<br>Do not share this code with anyone.</p>
                </div>
                <div class="footer"><p>Asfalis - Your Safety, Our Priority.</p></div>
            </div>
        </body>
        </html>
        """
        result = _dispatch_email(subject, to_email, html_body)
        if result:
            logger.info(f"OTP email dispatched for {to_email}")
        return result
    except Exception as e:
        logger.error(f"Failed to dispatch OTP email for {to_email}: {str(e)}")
        return False


def send_contact_added_email(to_email, contact_name, user_name, twilio_number, sandbox_code):
    """Sends an email to a newly added trusted contact with instructions.

    The WhatsApp sandbox section is only included when twilio_number and
    sandbox_code are both configured.  If they are missing the email is still
    delivered so the contact at least knows they were added.
    """
    try:
        subject = f"{user_name} added you as a Trusted Contact - Asfalis"

        # Build the WhatsApp join section only when Twilio is configured
        if twilio_number and sandbox_code:
            clean_number = twilio_number.replace('+', '').replace('-', '').replace(' ', '')
            encoded_code = sandbox_code.replace(' ', '%20')
            whatsapp_link = f"https://wa.me/{clean_number}?text={encoded_code}"
            whatsapp_section = f"""
                    <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
                    <h3>⚠️ Important Next Step</h3>
                    <p>To ensure you receive these emergency alerts on WhatsApp, you <strong>must</strong> join our sandbox environment.</p>
                    <p>1. Save this number: <strong>{twilio_number}</strong></p>
                    <p>2. Send the following code to that number on WhatsApp:</p>
                    <div class="code-box">{sandbox_code}</div>
                    <p>Or simply click the button below:</p>
                    <div style="text-align: center;">
                        <a href="{whatsapp_link}" class="button">Join on WhatsApp</a>
                    </div>"""
        else:
            logger.warning("Twilio number/sandbox not configured — sending contact email without WhatsApp section.")
            whatsapp_section = ""

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background-color: #f4f4f4; margin: 0; padding: 0; }}
                .container {{ max-width: 600px; margin: 20px auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
                .header {{ background-color: #4CAF50; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 30px; color: #333333; line-height: 1.6; }}
                .button {{ display: inline-block; padding: 12px 24px; background-color: #25D366; color: white; text-decoration: none; border-radius: 5px; font-weight: bold; margin-top: 20px; }}
                .footer {{ background-color: #eeeeee; color: #777777; padding: 15px; text-align: center; font-size: 12px; }}
                .code-box {{ background-color: #f9f9f9; border: 1px solid #ddd; padding: 10px; font-family: monospace; font-size: 16px; margin: 10px 0; display: inline-block; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header"><h1>You're a Trusted Contact 🛡️</h1></div>
                <div class="content">
                    <p>Hello <strong>{contact_name}</strong>,</p>
                    <p><strong>{user_name}</strong> has added you as a trusted contact in <strong>Asfalis</strong>, their personal safety app.</p>
                    <p>This means you will receive immediate alerts with their location if they trigger an SOS.</p>
                    {whatsapp_section}
                </div>
                <div class="footer"><p>Asfalis - Your Safety, Our Priority.</p></div>
            </div>
        </body>
        </html>
        """
        result = _dispatch_email(subject, to_email, html_body)
        if result:
            logger.info(f"Contact notification dispatched for {to_email}")
        return result
    except Exception as e:
        logger.error(f"Failed to dispatch contact notification for {to_email}: {str(e)}")
        return False
