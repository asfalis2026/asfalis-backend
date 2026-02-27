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
    client.post('/api/auth/register/phone', json={
        "phone_number": "+919876543210",
        "password": "password123",
        "full_name": "Auth User",
        "country": "India"
    })
    
    # Manually verify the user in DB (OTP verification is handled by Android app)
    from app.models.user import User
    from app.extensions import db
    user = User.query.filter_by(phone="+919876543210").first()
    if user:
        user.is_verified = True
        db.session.commit()

    resp = client.post('/api/auth/login/phone', json={
        "phone_number": "+919876543210",
        "password": "password123"
    })
        
    data = json.loads(resp.data)
    token = data['data']['access_token']
    return {'Authorization': f'Bearer {token}'}
