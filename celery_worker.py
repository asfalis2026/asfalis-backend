from app import create_app

app = create_app()
celery = app.extensions["celery"]

# Explicitly import tasks to ensure they are registered
import app.services.email_service
import app.services.sms_service
import app.services.whatsapp_service
import app.services.fcm_service
