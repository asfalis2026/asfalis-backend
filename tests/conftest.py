"""FastAPI test configuration — replaces Flask test_client with httpx TestClient."""

import pytest
import os

os.environ['FLASK_TESTING'] = 'False'  # no longer needed
os.environ['DATABASE_URL'] = 'sqlite:///test_asfalis.db'
os.environ['JWT_SECRET_KEY'] = 'test-jwt-secret'
os.environ['SECRET_KEY'] = 'test-secret'

from fastapi.testclient import TestClient
from app.main import app, socketio_app
from app.database import Base, engine, ScopedSession
from sqlalchemy import select


@pytest.fixture(scope='function')
def client():
    """Create a fresh test database and return the FastAPI test client."""
    Base.metadata.create_all(bind=engine)
    with TestClient(socketio_app) as c:
        yield c
    ScopedSession.remove()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def auth_header(client):
    """Register and verify a user, return the Authorization header."""
    # Register
    client.post('/api/auth/register/phone', json={
        "phone_number": "+919876543210",
        "password": "password123",
        "full_name": "Auth User",
        "country": "India"
    })

    # Manually verify in DB
    from app.models.user import User
    user = ScopedSession.scalar(select(User).where(User.phone == "+919876543210"))
    if user:
        user.is_verified = True
        ScopedSession.commit()

    # Login
    resp = client.post('/api/auth/login/phone', json={
        "phone_number": "+919876543210",
        "password": "password123"
    })
    data = resp.json()
    token = data['data']['access_token']
    return {'Authorization': f'Bearer {token}'}
