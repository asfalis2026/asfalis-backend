
import os
from datetime import timedelta

def get_env(key, default, type_cast=str):
    value = os.environ.get(key)
    if value is None or value.strip() == '':
        return default
    try:
        return type_cast(value)
    except (ValueError, TypeError):
        return default

class Config:
    DEBUG = os.environ.get('DEBUG', 'false').lower() == 'true'

    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///Asfalis.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'jwt-secret-key'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(seconds=get_env('JWT_ACCESS_TOKEN_EXPIRES', 900, int))
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(seconds=get_env('JWT_REFRESH_TOKEN_EXPIRES', 2592000, int))
    # Long-lived SOS token: issued at login, stored by the app, used ONLY for /sos/trigger
    # so that emergency alerts always work even when the regular access token has expired.
    JWT_SOS_TOKEN_EXPIRES_DAYS = get_env('JWT_SOS_TOKEN_EXPIRES_DAYS', 30, int)
    
    OTP_EXPIRY_SECONDS = get_env('OTP_EXPIRY_SECONDS', 300, int)
    MAX_OTP_ATTEMPTS = get_env('MAX_OTP_ATTEMPTS', 5, int)
    
    TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
    TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER')
    TWILIO_VERIFY_SERVICE_SID = os.environ.get('TWILIO_VERIFY_SERVICE_SID')
    # Separate WhatsApp account credentials (Account 2)
    TWILIO_WA_ACCOUNT_SID = os.environ.get('TWILIO_WA_ACCOUNT_SID')
    TWILIO_WA_AUTH_TOKEN = os.environ.get('TWILIO_WA_AUTH_TOKEN')
    TWILIO_WHATSAPP_FROM = os.environ.get('TWILIO_WHATSAPP_FROM', 'whatsapp:+14155238886')
    TWILIO_SANDBOX_CODE = os.environ.get('TWILIO_SANDBOX_CODE', 'join <sandbox-code>')
    
    # Flask-Limiter Storage (in-memory)
    RATELIMIT_STORAGE_URI = os.environ.get('RATELIMIT_STORAGE_URI', 'memory://')
    RATELIMIT_SWALLOW_ERRORS = True

    FIREBASE_CREDENTIALS_PATH = os.environ.get('FIREBASE_CREDENTIALS_PATH')
    FIREBASE_CREDENTIALS_JSON = os.environ.get('FIREBASE_CREDENTIALS_JSON')
    
    MAX_TRUSTED_CONTACTS = get_env('MAX_TRUSTED_CONTACTS', 5, int)
    SOS_COOLDOWN_SECONDS = get_env('SOS_COOLDOWN_SECONDS', 20, int)
    # Duration (seconds) of the SOS countdown shown in the app before dispatching.
    # Returned in every POST /api/sos/trigger response so the app doesn't
    # hard-code it.  Android IotSosTracker and SosViewModel both read this value.
    SOS_COUNTDOWN_SECONDS = get_env('SOS_COUNTDOWN_SECONDS', 10, int)

    # Set to 'true' to enforce per-device IMEI binding and the 12-hour
    # handset-transfer cooldown on login.  Set to 'false' (default) to
    # bypass all IMEI checks — useful during development / testing.
    IMEI_BINDING_ENABLED = os.environ.get('IMEI_BINDING_ENABLED', 'false').lower() == 'true'

    # IoT wearable (ESP32) button double-tap window.
    # Two button-press events received within this many seconds = cancel SOS.
    # A single press outside this window = trigger SOS countdown.
    IOT_DOUBLE_TAP_WINDOW_SECONDS = get_env('IOT_DOUBLE_TAP_WINDOW_SECONDS', 1.5, float)
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()


# Module-level singleton so services can do:
#   from app.config import settings
#   account_sid = settings.TWILIO_ACCOUNT_SID
# instead of current_app.config.get('TWILIO_ACCOUNT_SID')
# Use @property or just assign direct for simple case
settings = Config
