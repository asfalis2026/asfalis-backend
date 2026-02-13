import json

def test_trigger_sos(client, auth_header):
    """Test triggering an SOS alert."""
    # Add a contact first to avoid NO_CONTACTS error
    client.post('/api/contacts', headers=auth_header, json={
        "name": "Mom",
        "phone": "+1234567890",
        "relationship": "Parent",
        "is_primary": True
    })

    response = client.post('/api/sos/trigger', headers=auth_header, json={
        "latitude": 37.7749,
        "longitude": -122.4194,
        "trigger_type": "manual"
    })
    # Might mock notification services, but basic endpoint should work
    assert response.status_code == 201
    data = json.loads(response.data)
    assert data['success'] is True
    assert "alert_id" in data['data']

def test_get_sos_history(client, auth_header):
    """Test retrieving SOS history."""
    # Add a contact first
    client.post('/api/contacts', headers=auth_header, json={
        "name": "Dad",
        "phone": "+0987654321",
        "relationship": "Parent"
    })
    
    # Create one first
    client.post('/api/sos/trigger', headers=auth_header, json={
        "latitude": 37.7749,
        "longitude": -122.4194,
        "trigger_type": "manual"
    })
    
    response = client.get('/api/sos/history', headers=auth_header)
    assert response.status_code == 200
    data = json.loads(response.data)
    assert isinstance(data['data'], list)
    assert len(data['data']) >= 1
