
from app import create_app
from flask_mail import Message
from app.extensions import mail
import sys

app = create_app()

def test_email():
    recipient = input("Enter recipient email: ")
    with app.app_context():
        try:
            print(f"Attempting to send email to {recipient}...")
            print(f"Server: {app.config['MAIL_SERVER']}:{app.config['MAIL_PORT']}")
            print(f"Username: {app.config['MAIL_USERNAME']}")
            print(f"TLS: {app.config['MAIL_USE_TLS']}")
            
            msg = Message(
                subject="Test Email from Raksha Backend",
                sender=app.config['MAIL_USERNAME'],
                recipients=[recipient],
                body="This is a test email to verify SMTP configuration."
            )
            mail.send(msg)
            print("✅ Email sent successfully!")
        except Exception as e:
            print(f"❌ Failed to send email: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_email()
