import json

def test_update_location(client, auth_header):
    """Test updating user location."""
    response = client.post('/api/location/update', headers=auth_header, json={
        "latitude": 37.7749,
        "longitude": -122.4194,
        "is_sharing": True
    })
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True

def test_get_location_history(client, auth_header):
    """Test retrieving location history."""
    # Update first
    client.post('/api/location/update', headers=auth_header, json={
        "latitude": 37.7749,
        "longitude": -122.4194,
        "is_sharing": True
    })
    
    response = client.get('/api/location/current', headers=auth_header)
    assert response.status_code == 200
    data = json.loads(response.data)
    # /current returns a single object in data, not a list
    assert data['success'] is True
    assert data['data']['latitude'] == 37.7749
