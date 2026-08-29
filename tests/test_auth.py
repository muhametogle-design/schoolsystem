"""Health + authentication contract."""

from __future__ import annotations


def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["attendance_deadline"] == "12:00"
    assert body["alarm_audit_time"] == "15:00"


def test_login_success_returns_role_and_school(client):
    res = client.post("/api/auth/login", json={"email": "inspector@education.gov", "password": "State@2026"})
    assert res.status_code == 200
    body = res.json()
    assert body["user"]["role"] == "state_inspector"
    assert body["user"]["school_id"] is None  # NULL => State Gov admin


def test_login_rejects_bad_password(client):
    res = client.post("/api/auth/login", json={"email": "inspector@education.gov", "password": "wrong"})
    assert res.status_code == 401


def test_me_requires_token(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_roundtrip(client, greenfield_manager_headers):
    res = client.get("/api/auth/me", headers=greenfield_manager_headers)
    assert res.status_code == 200
    assert res.json()["role"] == "school_manager"
    assert res.json()["school_name"] == "Greenfield Academy"


def test_websocket_connects_with_token(client, state_token):
    with client.websocket_connect(f"/ws?token={state_token}") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "connected"
        assert msg["payload"]["role"] == "state_inspector"
