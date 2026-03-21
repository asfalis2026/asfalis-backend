import pytest

def test_health_check(client):
    """Test that the application starts and database responds via the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "Asfalis-backend"
    assert data["database"] == "ok"


def test_auth_registration(client):
    """Test user registration endpoint with Pydantic validation."""
    response = client.post("/api/auth/register/phone", json={
        "full_name": "Test User",
        "phone_number": "+1234567890",
        "country": "USA",
        "password": "securepassword123"
    })
    
    # We expect 201 Created and successful response form Asfalis API structure
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "success"
    assert "user_id" in data["data"]


def test_invalid_auth_registration(client):
    """Test that Pydantic properly blocks invalid registration payloads."""
    response = client.post("/api/auth/register/phone", json={
        "full_name": "Too Short",
        # Missing required phone_number field
        "country": "USA",
        "password": "pass" # Too short password
    })
    
    # FastAPI automatically throws 422 Unprocessable Entity
    # (now caught by our RequestValidationError handler to return {"success": False, ...})
    assert response.status_code == 422
    data = response.json()
    assert data["success"] is False
    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_ERROR"
