import pytest
import json
import os

# Set testing environment before importing app to avoid eventlet issues
os.environ['FLASK_TESTING'] = 'True'

from app import create_app, db
from app.config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    CELERY = {'task_always_eager': True} # Use eager mode for tests
    MAIL_SUPPRESS_SEND = True

@pytest.fixture
def app():
    app = create_app(TestConfig)
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def runner(app):
    return app.test_cli_runner()

@pytest.fixture
def auth_header(client):
    """Register and login a user, returning the auth header."""
    # Register
    client.post('/api/auth/register/email', json={
        "email": "auth_test@example.com",
        "password": "password123",
        "full_name": "Auth User",
        "country": "India"
    })
    
    # Login (skipping verify for now as verify endpoint requires OTP which we can't easily get without mocking)
    # Be careful: In real app, user might need to be verified to login. 
    # Let's check auth.py: login checks `if not user`. It doesn't seem to enforce `is_verified` for login? 
    # Wait, `verify-email-otp` sets `is_verified=True`. 
    # If login doesn't check `is_verified`, we are good. 
    # Let's assume for test simplicity we can login immediately or we check if we need verify.
    # Looking at auth.py line 160-166, it checks password but not is_verified.
    
    resp = client.post('/api/auth/login/email', json={
        "email": "auth_test@example.com",
        "password": "password123"
    })
    
    if resp.status_code != 200:
        # Fallback if verify is needed: Manually verify in DB
        from app.models.user import User
        from app.extensions import db
        user = User.query.filter_by(email="auth_test@example.com").first()
        if user:
            user.is_verified = True
            db.session.commit()
        # Try login again
        resp = client.post('/api/auth/login/email', json={
            "email": "auth_test@example.com",
            "password": "password123"
        })
        
    data = json.loads(resp.data)
    token = data['data']['access_token']
    return {'Authorization': f'Bearer {token}'}
