
from flask import current_app
import logging
import re
import json
import ssl
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

# SendGrid v3 Mail Send endpoint – one fast HTTP POST instead of 7+ SMTP
# round-trips (TCP → TLS → AUTH → MAIL FROM → RCPT TO → DATA → QUIT).
_SENDGRID_API_URL = "https://api.sendgrid.com/v3/mail/send"
_TIMEOUT_SECONDS = 15

# Build a proper SSL context using certifi's CA bundle.
# macOS Python from python.org ships without system certs, which causes
# "CERTIFICATE_VERIFY_FAILED" on every HTTPS call via urllib.
try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CTX = ssl.create_default_context()


def _strip_html(html: str) -> str:
    """Naive HTML-to-plain-text conversion for the text/plain fallback."""
    text = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</p>', '\n\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _dispatch_email(subject, to_email, html_body):
    """Send an email via the **SendGrid v3 HTTP API**.

    This replaces the old Flask-Mail / SMTP approach which was unreliable
    because each send required 7+ network round-trips to smtp.sendgrid.net.
    The HTTP API is a single POST with a 15-second timeout.
    """
    sender = current_app.config.get('MAIL_SENDER')
    api_key = current_app.config.get('MAIL_PASSWORD')        # SendGrid API key

    if not sender or not api_key:
        logger.error(
            "Email not sent — MAIL_SENDER and/or MAIL_PASSWORD are not "
            "configured in environment variables. "
            f"(MAIL_SENDER={'set' if sender else 'MISSING'}, "
            f"MAIL_PASSWORD={'set' if api_key else 'MISSING'})"
        )
        return False

    if not to_email:
        logger.error("Email not sent — recipient email address is empty.")
        return False

    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": sender, "name": "Asfalis"},
        "reply_to": {"email": sender, "name": "Asfalis"},
        "subject": subject,
        "content": [
            {"type": "text/plain", "value": _strip_html(html_body)},
            {"type": "text/html",  "value": html_body},
        ],
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        _SENDGRID_API_URL,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS, context=_SSL_CTX) as resp:
            status = resp.status
            # 202 = queued for delivery, 200 = sent
            if status in (200, 202):
                logger.info(f"Email sent to {to_email} (subject: {subject!r}) [HTTP {status}]")
                return True
            body = resp.read().decode()
            logger.error(f"SendGrid returned HTTP {status} for {to_email}: {body}")
            return False
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        logger.error(
            f"SendGrid HTTP {e.code} for {to_email}: {body}",
            exc_info=True,
        )
        return False
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}", exc_info=True)
        return False


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
