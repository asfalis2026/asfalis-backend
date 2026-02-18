import pytest
from app.models.user import User
from app.extensions import db
import json

def test_sos_message_update(client, auth_header):
    """Test updating and retrieving the SOS message."""
    
    # 1. Update SOS message
    response = client.put('/user/profile', headers=auth_header, json={
        'sos_message': 'Help me! This is an emergency!'
    })
    assert response.status_code == 200
    assert response.json['success'] == True

    # 2. Verify update via GET
    response = client.get('/user/profile', headers=auth_header)
    assert response.status_code == 200
    assert response.json['data']['sos_message'] == 'Help me! This is an emergency!'

    # 3. Test validation (max length 50)
    long_message = 'a' * 51
    response = client.put('/user/profile', headers=auth_header, json={
        'sos_message': long_message
    })
    assert response.status_code == 400
    assert response.json['success'] == False
    assert 'sos_message' in response.json['error']['details']

    # 4. Verify original message is preserved after failed update
    response = client.get('/user/profile', headers=auth_header)
    assert response.json['data']['sos_message'] == 'Help me! This is an emergency!'
