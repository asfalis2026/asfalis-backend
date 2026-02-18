
import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///Asfalis.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'jwt-secret-key'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(seconds=int(os.environ.get('JWT_ACCESS_TOKEN_EXPIRES', 900)))
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(seconds=int(os.environ.get('JWT_REFRESH_TOKEN_EXPIRES', 2592000)))
    
    OTP_EXPIRY_SECONDS = int(os.environ.get('OTP_EXPIRY_SECONDS', 300))
    MAX_OTP_ATTEMPTS = int(os.environ.get('MAX_OTP_ATTEMPTS', 5))
    
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    
    TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
    TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER')
    TWILIO_WHATSAPP_FROM = os.environ.get('TWILIO_WHATSAPP_FROM', 'whatsapp:+14155238886')
    TWILIO_SANDBOX_CODE = os.environ.get('TWILIO_SANDBOX_CODE', 'join <sandbox-code>')
    
    
    # Background Task Configuration
    CELERY = dict(
        broker_url=os.environ.get('CELERY_BROKER_URL', 'redis://redis:6379/0'),
        result_backend=os.environ.get('CELERY_RESULT_BACKEND', 'redis://redis:6379/0'),
        task_ignore_result=True,
    )
    
    # Flask-Limiter Storage
    RATELIMIT_STORAGE_URI = os.environ.get('RATELIMIT_STORAGE_URI') or os.environ.get('REDIS_URL', 'redis://redis:6379/0')

    # Fix for Docker environment: If running in Docker and URL is localhost, switch to 'redis'
    if os.path.exists('/.dockerenv'):
        if 'localhost' in RATELIMIT_STORAGE_URI:
            RATELIMIT_STORAGE_URI = RATELIMIT_STORAGE_URI.replace('localhost', 'redis')
        
        # Also update CELERY broker if it was defaulted/loaded as localhost
        if 'localhost' in CELERY['broker_url']:
            CELERY['broker_url'] = CELERY['broker_url'].replace('localhost', 'redis')
        if 'localhost' in CELERY['result_backend']:
            CELERY['result_backend'] = CELERY['result_backend'].replace('localhost', 'redis')


    FIREBASE_CREDENTIALS_PATH = os.environ.get('FIREBASE_CREDENTIALS_PATH')
    FIREBASE_CREDENTIALS_JSON = os.environ.get('FIREBASE_CREDENTIALS_JSON')
    
    MAX_TRUSTED_CONTACTS = int(os.environ.get('MAX_TRUSTED_CONTACTS', 5))
