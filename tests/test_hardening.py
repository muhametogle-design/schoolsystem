"""Production hardening: security headers, login throttling, safe 500s, health."""

from __future__ import annotations


def test_security_headers_present(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert res.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert res.headers["Permissions-Policy"].startswith("geolocation=()")


def test_health_reports_version_and_uptime(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["version"]
    assert isinstance(body["uptime_seconds"], (int, float))
    assert body["alarm_audit_time"] == "15:00"


def test_login_throttle_blocks_brute_force(client):
    """Five failed sign-ins for one identity → the sixth is throttled with 429."""
    payload = {"email": "brute.force@test.dev", "password": "wrong"}
    for _ in range(5):
        res = client.post("/api/auth/login", json=payload)
        assert res.status_code == 401
    blocked = client.post("/api/auth/login", json=payload)
    assert blocked.status_code == 429

    # A different identity is unaffected, and success clears the window
    ok = client.post(
        "/api/auth/login",
        json={"email": "inspector@education.gov", "password": "State@2026"},
    )
    assert ok.status_code == 200


def test_login_failure_message_is_uniform(client):
    """Never reveal whether the account exists."""
    unknown = client.post(
        "/api/auth/login", json={"email": "ghost@nowhere.dev", "password": "x"}
    )
    known = client.post(
        "/api/auth/login", json={"email": "inspector@education.gov", "password": "x"}
    )
    assert unknown.status_code == known.status_code == 401
    assert unknown.json()["detail"] == known.json()["detail"]
