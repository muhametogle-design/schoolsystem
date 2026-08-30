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
    assert body["user"]["role"] == "inspector"
    assert body["user"]["school_id"] is None  # NULL => State Gov admin


def test_login_rejects_bad_password(client):
    res = client.post("/api/auth/login", json={"email": "inspector@education.gov", "password": "wrong"})
    assert res.status_code == 401


def test_me_requires_token(client):
    client.cookies.clear()  # ignore any lingering session cookie
    assert client.get("/api/auth/me").status_code == 401


def test_cookie_fallback_authentication(client):
    """Behind proxies/frames that strip the Authorization header, the HttpOnly
    cookie set at login must authenticate the session on its own."""
    res = client.post(
        "/api/auth/login",
        json={"email": "inspector@education.gov", "password": "State@2026"},
    )
    assert res.status_code == 200
    assert "schoolsystem_token" in res.cookies

    me = client.get("/api/auth/me")  # no Authorization header — cookie only
    assert me.status_code == 200
    assert me.json()["role"] == "inspector"

    # State portal also authenticates via cookie
    cmap = client.get("/api/v1/state/compliance-map")
    assert cmap.status_code == 200

    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401


def test_me_roundtrip(client, greenfield_manager_headers):
    res = client.get("/api/auth/me", headers=greenfield_manager_headers)
    assert res.status_code == 200
    assert res.json()["role"] == "school_manager"
    assert res.json()["school_name"] == "ALQALAM SCHOOLS"


def test_websocket_connects_with_token(client, state_token):
    with client.websocket_connect(f"/ws?token={state_token}") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "connected"
        assert msg["payload"]["role"] == "inspector"


def test_websocket_cookie_fallback(client):
    """Live academic updates still work when a mobile browser has no stored token."""
    res = client.post(
        "/api/auth/login",
        json={"email": "inspector@education.gov", "password": "State@2026"},
    )
    assert res.status_code == 200
    with client.websocket_connect("/ws") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "connected"
        assert msg["payload"]["role"] == "inspector"
