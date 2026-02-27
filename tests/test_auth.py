import json

def test_register_phone(client):
    """Test user registration with phone number."""
    response = client.post('/api/auth/register/phone', json={
        "phone_number": "+919999999999",
        "password": "password123",
        "full_name": "Test User",
        "country": "India"
    })
    assert response.status_code in [200, 201]
    data = json.loads(response.data)
    assert data.get('success') is True
    assert "message" in data
    # OTP should be returned in the response for the Android app to send via SMS
    assert "otp_code" in data.get('data', {})

def test_login_phone(client):
    """Test user login with phone number (wrong password should fail)."""
    # 1. Register first
    client.post('/api/auth/register/phone', json={
        "phone_number": "+918888888888",
        "password": "password123",
        "full_name": "Login User",
        "country": "India"
    })
    
    # 2. Test that login with wrong credentials fails
    response = client.post('/api/auth/login/phone', json={
        "phone_number": "+918888888888",
        "password": "wrongpassword"
    })
    assert response.status_code == 401

def test_login_phone_unverified(client):
    """Test that unverified user cannot login."""
    client.post('/api/auth/register/phone', json={
        "phone_number": "+917777777777",
        "password": "password123",
        "full_name": "Unverified User",
        "country": "India"
    })
    response = client.post('/api/auth/login/phone', json={
        "phone_number": "+917777777777",
        "password": "password123"
    })
    assert response.status_code == 403
    data = json.loads(response.data)
    assert data['error']['code'] == 'PHONE_NOT_VERIFIED'

def test_health_check(client):
    """Test health check endpoint."""
    response = client.get('/health')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'healthy'
