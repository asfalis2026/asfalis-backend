
import os
from datetime import timedelta

# Detect if running inside a Docker container
_in_docker = os.path.exists('/.dockerenv')

def _resolve_redis_url(url: str) -> str:
    """
    If running inside Docker, replace 'localhost' with 'redis' (the service name).
    This handles the case where .env sets localhost but the app runs in Docker Compose.
    """
    if _in_docker and url and 'localhost' in url:
        return url.replace('localhost', 'redis')
    return url

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
    
    # Background Task Configuration (Celery)
    # Priority: explicit env var > Docker-resolved REDIS_URL > localhost default
    _redis_url = _resolve_redis_url(os.environ.get('REDIS_URL', 'redis://localhost:6379/0'))
    CELERY = dict(
        broker_url=_resolve_redis_url(os.environ.get('CELERY_BROKER_URL', _redis_url)),
        result_backend=_resolve_redis_url(os.environ.get('CELERY_RESULT_BACKEND', _redis_url)),
        task_ignore_result=True,
    )
    
    # Flask-Limiter Storage
    # Falls back to in-memory if no Redis URL is configured (safe for local dev without Redis)
    _ratelimit_url = os.environ.get('RATELIMIT_STORAGE_URI') or _redis_url
    RATELIMIT_STORAGE_URI = _resolve_redis_url(_ratelimit_url) if _ratelimit_url else 'memory://'
    RATELIMIT_SWALLOW_ERRORS = True  # Don't crash the app if Redis is unavailable

    FIREBASE_CREDENTIALS_PATH = os.environ.get('FIREBASE_CREDENTIALS_PATH')
    FIREBASE_CREDENTIALS_JSON = os.environ.get('FIREBASE_CREDENTIALS_JSON')
    
    MAX_TRUSTED_CONTACTS = int(os.environ.get('MAX_TRUSTED_CONTACTS', 5))
