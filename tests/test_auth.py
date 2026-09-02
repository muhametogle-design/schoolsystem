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


# --- Payload-format tolerance & token failure modes (regression: 500s) -------


def test_login_accepts_form_encoded_username(client):
    """OAuth2-style form posts (username/password) must work, not 422/500."""
    res = client.post(
        "/api/auth/login",
        data={"username": "inspector@education.gov", "password": "State@2026"},
    )
    assert res.status_code == 200
    assert res.json()["user"]["role"] == "inspector"


def test_login_accepts_form_encoded_email_field(client):
    res = client.post(
        "/api/auth/login",
        data={"email": "inspector@education.gov", "password": "State@2026"},
    )
    assert res.status_code == 200


def test_oauth2_token_route(client):
    """Swagger UI's Authorize button posts x-www-form-urlencoded to /token."""
    res = client.post(
        "/api/auth/token",
        data={"username": "inspector@education.gov", "password": "State@2026"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_empty_body_is_422_not_500(client):
    assert client.post("/api/auth/login", content=b"") .status_code == 422
    assert client.post("/api/auth/login", json={}).status_code == 422
    assert client.post("/api/auth/login", content=b"not-json", headers={"Content-Type": "application/json"}).status_code == 422


def test_me_with_garbage_token_is_401_not_500(client):
    client.cookies.clear()
    res = client.get("/api/auth/me", headers={"Authorization": "Bearer not.a.jwt"})
    assert res.status_code == 401


def test_me_with_wrong_signature_is_401_not_500(client):
    import jwt as pyjwt

    client.cookies.clear()
    forged = pyjwt.encode({"sub": "1", "role": "state_admin", "school_id": None}, "attacker-key", algorithm="HS256")
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert res.status_code == 401


def test_me_with_expired_token_is_401_not_500(client):
    import datetime as dt

    import jwt as pyjwt

    from app.core.config import settings

    client.cookies.clear()
    past = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=2)
    expired = pyjwt.encode(
        {"sub": "1", "role": "inspector", "school_id": None, "iat": past, "exp": past + dt.timedelta(minutes=5)},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert res.status_code == 401
    assert "expired" in res.json()["detail"].lower()


def test_decode_access_token_error_types():
    """decode_access_token must raise domain errors, never leak PyJWT types."""
    import pytest

    from app.core.security import TokenError, TokenExpiredError, create_access_token, decode_access_token

    token = create_access_token(user_id=42, role="inspector", school_id=None)
    payload = decode_access_token(token)
    assert payload["sub"] == "42"
    assert payload["role"] == "inspector"
    assert isinstance(token, str)

    with pytest.raises(TokenError):
        decode_access_token("garbage.token.value")
    assert issubclass(TokenExpiredError, TokenError)
