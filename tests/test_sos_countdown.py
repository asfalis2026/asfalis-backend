"""
Tests for the SOS countdown flow (Step 3 in the diagram).

Flow under test:
  POST /api/sos/trigger          → creates alert with status='countdown'
                                   returns countdown_seconds + countdown_expires_at
  GET  /api/sos/countdown/{id}   → polls server-side countdown state
  POST /api/sos/cancel           → cancels the countdown alert
  POST /api/sos/send-now         → dispatches alert (mocked, no real WhatsApp)
"""

import pytest
from unittest.mock import patch
from sqlalchemy.orm import Session
from app.models.trusted_contact import TrustedContact
from app.database import ScopedSession
from app.services.sos_service import COUNTDOWN_SECONDS


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _add_emergency_contact(user_id: str):
    """Insert a dummy trusted contact so /trigger doesn't block with NO_CONTACTS."""
    contact = TrustedContact(
        user_id=user_id,
        name="Emergency Contact",
        phone="+910000000000",
        relationship="friend",
        is_verified=True,
    )
    ScopedSession.add(contact)
    ScopedSession.commit()
    return contact


def _get_user_id(client, auth_header) -> str:
    """Fetch authenticated user's ID from /api/user/profile."""
    resp = client.get("/api/user/profile", headers=auth_header)
    assert resp.status_code == 200, f"Profile fetch failed: {resp.text}"
    return resp.json()["data"]["user_id"]  # profile returns 'user_id', not 'id'


# ─── Tests ───────────────────────────────────────────────────────────────────

class TestSosCountdownTrigger:
    """POST /api/sos/trigger — countdown metadata in response."""

    def test_trigger_returns_countdown_metadata(self, client, auth_header):
        user_id = _get_user_id(client, auth_header)
        _add_emergency_contact(user_id)

        resp = client.post("/api/sos/trigger", json={
            "latitude": 12.9716,
            "longitude": 77.5946,
            "trigger_type": "manual",
        }, headers=auth_header)

        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]

        assert data["status"] == "countdown"
        assert "alert_id" in data
        assert "countdown_seconds" in data, "countdown_seconds must be in trigger response"
        assert "countdown_expires_at" in data, "countdown_expires_at must be in trigger response"
        assert data["countdown_seconds"] == COUNTDOWN_SECONDS
        assert data["countdown_seconds"] == 10
        assert data["countdown_expires_at"].endswith("Z")

    def test_trigger_without_contacts_rejected(self, client, auth_header):
        resp = client.post("/api/sos/trigger", json={
            "latitude": 12.9716,
            "longitude": 77.5946,
        }, headers=auth_header)
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "NO_CONTACTS"

    def test_trigger_requires_auth(self, client):
        resp = client.post("/api/sos/trigger", json={
            "latitude": 12.9716,
            "longitude": 77.5946,
        })
        # FastAPI returns 422 when the required 'authorization' header is absent
        # (the dependency uses Header(...) which is a required field)
        assert resp.status_code in (401, 422)


class TestSosCountdownStatus:
    """GET /api/sos/countdown/{alert_id} — countdown status polling."""

    def test_countdown_is_active_immediately_after_trigger(self, client, auth_header):
        user_id = _get_user_id(client, auth_header)
        _add_emergency_contact(user_id)

        # Trigger
        trigger_resp = client.post("/api/sos/trigger", json={
            "latitude": 13.0827, "longitude": 80.2707,
        }, headers=auth_header)
        assert trigger_resp.status_code == 201
        alert_id = trigger_resp.json()["data"]["alert_id"]

        # Poll countdown immediately — should still be active
        poll_resp = client.get(f"/api/sos/countdown/{alert_id}", headers=auth_header)
        assert poll_resp.status_code == 200, poll_resp.text
        d = poll_resp.json()["data"]

        assert d["status"] == "countdown"
        assert d["is_active"] is True
        assert d["seconds_remaining"] > 0
        assert d["seconds_remaining"] <= COUNTDOWN_SECONDS
        assert d["countdown_seconds"] == COUNTDOWN_SECONDS
        assert "countdown_expires_at" in d

    def test_countdown_status_not_found_for_invalid_id(self, client, auth_header):
        resp = client.get("/api/sos/countdown/nonexistent-id", headers=auth_header)
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "NOT_FOUND"

    def test_countdown_status_requires_auth(self, client, auth_header):
        # First create a real alert to get a valid ID
        user_id = _get_user_id(client, auth_header)
        _add_emergency_contact(user_id)
        trigger_resp = client.post("/api/sos/trigger", json={
            "latitude": 0.0, "longitude": 0.0,
        }, headers=auth_header)
        alert_id = trigger_resp.json()["data"]["alert_id"]

        # Now try without auth — FastAPI raises 422 for missing required header
        resp = client.get(f"/api/sos/countdown/{alert_id}")
        assert resp.status_code in (401, 422)

    def test_countdown_status_after_cancel_shows_cancelled(self, client, auth_header):
        user_id = _get_user_id(client, auth_header)
        _add_emergency_contact(user_id)

        trigger_resp = client.post("/api/sos/trigger", json={
            "latitude": 0.0, "longitude": 0.0,
        }, headers=auth_header)
        alert_id = trigger_resp.json()["data"]["alert_id"]

        # Cancel it
        client.post("/api/sos/cancel", json={"alert_id": alert_id}, headers=auth_header)

        # Now poll — should show cancelled, not active
        poll_resp = client.get(f"/api/sos/countdown/{alert_id}", headers=auth_header)
        assert poll_resp.status_code == 200
        d = poll_resp.json()["data"]
        assert d["status"] == "cancelled"
        assert d["is_active"] is False
        assert d["seconds_remaining"] == 0


class TestSosCancel:
    """POST /api/sos/cancel — cancel during countdown."""

    def test_cancel_active_countdown(self, client, auth_header):
        user_id = _get_user_id(client, auth_header)
        _add_emergency_contact(user_id)

        trigger_resp = client.post("/api/sos/trigger", json={
            "latitude": 0.0, "longitude": 0.0,
        }, headers=auth_header)
        alert_id = trigger_resp.json()["data"]["alert_id"]

        cancel_resp = client.post("/api/sos/cancel",
                                  json={"alert_id": alert_id},
                                  headers=auth_header)
        assert cancel_resp.status_code == 200
        assert cancel_resp.json()["success"] is True

    def test_double_cancel_fails(self, client, auth_header):
        user_id = _get_user_id(client, auth_header)
        _add_emergency_contact(user_id)

        trigger_resp = client.post("/api/sos/trigger", json={
            "latitude": 0.0, "longitude": 0.0,
        }, headers=auth_header)
        alert_id = trigger_resp.json()["data"]["alert_id"]

        client.post("/api/sos/cancel", json={"alert_id": alert_id}, headers=auth_header)
        second = client.post("/api/sos/cancel", json={"alert_id": alert_id}, headers=auth_header)
        assert second.status_code == 400
        assert second.json()["error"]["code"] == "CANCEL_ERROR"


class TestSosSendNow:
    """POST /api/sos/send-now — dispatch after countdown expires."""

    def test_send_now_dispatches_alert(self, client, auth_header):
        user_id = _get_user_id(client, auth_header)
        _add_emergency_contact(user_id)

        trigger_resp = client.post("/api/sos/trigger", json={
            "latitude": 0.0, "longitude": 0.0,
        }, headers=auth_header)
        alert_id = trigger_resp.json()["data"]["alert_id"]

        # Import the whatsapp module first so the patch target resolves correctly
        # (dispatch_sos does a local 'from app.services.whatsapp_service import ...'
        #  so we patch the function at its definition point in that module)
        import app.services.whatsapp_service as _ws
        with patch.object(_ws, "send_whatsapp_sync",
                          return_value={"success": True, "status": "sent",
                                        "error_code": None, "error_msg": None}):
            send_resp = client.post("/api/sos/send-now",
                                    json={"alert_id": alert_id},
                                    headers=auth_header)

        assert send_resp.status_code == 200, send_resp.text
        assert send_resp.json()["success"] is True

        # Countdown poll after dispatch should show 'sent', not active
        poll_resp = client.get(f"/api/sos/countdown/{alert_id}", headers=auth_header)
        d = poll_resp.json()["data"]
        assert d["status"] == "sent"
        assert d["is_active"] is False
