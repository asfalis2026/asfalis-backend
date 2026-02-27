
from app import create_app
from app.services.email_service import send_otp_email
import sys

app = create_app()

def test_email():
    recipient = input("Enter recipient email: ")
    with app.app_context():
        try:
            print(f"Attempting to send email to {recipient}...")
            result = send_otp_email(recipient, "123456")
            if result:
                print("✅ Email sent successfully!")
            else:
                print("❌ Email failed — check logs above.")
        except Exception as e:
            print(f"❌ Failed to send email: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_email()
