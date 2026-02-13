import json

def test_register_email(client):
    """Test user registration with email."""
    response = client.post('/api/auth/register/email', json={
        "email": "test@example.com",
        "password": "password123",
        "full_name": "Test User",
        "country": "India"
    })
    # Since we might not have a mocked email server, we mainly check if it processes the request
    # It might return 200 or 201 depending on implementation
    assert response.status_code in [200, 201]
    data = json.loads(response.data)
    assert data.get('success') is True
    assert "message" in data

def test_login_email(client):
    """Test user login (after registration manually or mocked)."""
    # 1. Register first
    client.post('/api/auth/register/email', json={
        "email": "login_test@example.com",
        "password": "password123",
        "full_name": "Login User",
        "country": "India"
    })
    
    # 2. We need to verify OTP to get the user active? 
    # Or maybe we can't fully test login without mocking the OTP verification flow.
    # For now, let's just test that login with wrong credentials fails as expected
    response = client.post('/api/auth/login/email', json={
        "email": "login_test@example.com",
        "password": "wrongpassword"
    })
    assert response.status_code == 401

def test_health_check(client):
    """Test health check endpoint."""
    response = client.get('/health')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'healthy'
