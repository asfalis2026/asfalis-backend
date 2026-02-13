import json

def test_add_contact(client, auth_header):
    """Test adding a trusted contact."""
    response = client.post('/api/contacts', headers=auth_header, json={
        "name": "Mom",
        "phone": "+1234567890",
        "relationship": "Parent",
        "is_primary": True,
        "email": "mom@example.com"
    })
    assert response.status_code == 201
    data = json.loads(response.data)
    assert data['success'] is True
    assert data['data']['name'] == "Mom"

def test_get_contacts(client, auth_header):
    """Test retrieving contacts."""
    # Add one first
    client.post('/api/contacts', headers=auth_header, json={
        "name": "Dad",
        "phone": "+0987654321",
        "relationship": "Parent"
    })
    
    response = client.get('/api/contacts', headers=auth_header)
    assert response.status_code == 200
    data = json.loads(response.data)
    assert isinstance(data['data'], list)
    assert len(data['data']) >= 1

def test_delete_contact(client, auth_header):
    """Test deleting a contact."""
    # Add
    resp = client.post('/api/contacts', headers=auth_header, json={
        "name": "Brother",
        "phone": "+1122334455",
        "relationship": "Sibling"
    })
    contact_id = json.loads(resp.data)['data']['id']
    
    # Delete
    del_resp = client.delete(f'/api/contacts/{contact_id}', headers=auth_header)
    assert del_resp.status_code == 200
    
    # Verify gone
    get_resp = client.get('/api/contacts', headers=auth_header)
    contacts = json.loads(get_resp.data)['data']
    assert not any(c['id'] == contact_id for c in contacts)
