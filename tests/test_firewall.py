"""THE CRITICAL FIREWALL RULE — proven in code.

Under no circumstances can a State Government user access tuition rates,
billing configurations, student ledgers, outstanding balances or payment
transaction logs. Every attempt is rejected AND audited.
"""

from __future__ import annotations

from app.core.db import SessionLocal
from app.models import SecurityAuditLog

FINANCIAL_ROUTES = [
    ("GET", "/api/v1/school/finance/summary", None),
    ("GET", "/api/v1/school/finance/tuition-rates", None),
    ("GET", "/api/v1/school/finance/invoices", None),
    ("POST", "/api/v1/school/finance/invoices", {"student_id": 1, "description": "x", "amount_due": 10}),
    ("POST", "/api/v1/school/finance/invoices/1/payments", {"amount": 1, "payment_method": "Cash"}),
]


def test_state_role_blocked_from_every_financial_route(client, auth_headers):
    for method, url, body in FINANCIAL_ROUTES:
        res = client.request(method, url, headers=auth_headers, json=body)
        assert res.status_code == 403, f"{method} {url} leaked financial data: {res.status_code}"
        assert "FIREWALL" in res.json()["detail"]


def test_state_violations_are_audited(client, auth_headers):
    client.get("/api/v1/school/finance/summary", headers=auth_headers)
    with SessionLocal() as db:
        rows = (
            db.query(SecurityAuditLog)
            .filter(SecurityAuditLog.verdict == "BLOCKED", SecurityAuditLog.endpoint == "/api/v1/school/finance/summary")
            .all()
        )
        assert rows, "Firewall violation was not written to security_audit_log"


def test_teachers_blocked_from_financials(client, greenfield_teacher_headers):
    res = client.get("/api/v1/school/finance/summary", headers=greenfield_teacher_headers)
    assert res.status_code == 403


def test_school_roles_blocked_from_state_portal(client, greenfield_manager_headers, greenfield_teacher_headers):
    for headers in (greenfield_manager_headers, greenfield_teacher_headers):
        assert client.get("/api/v1/state/compliance-map", headers=headers).status_code == 403
        assert client.get("/api/v1/state/students/search?q=x", headers=headers).status_code == 403
        assert client.post("/api/v1/state/audit/run", headers=headers).status_code == 403


def test_tenant_isolation_between_schools(client, horizon_manager_headers, greenfield_manager_headers):
    """A tenant can never enumerate another tenant's students or classes."""
    gf = client.get("/api/v1/school/students", headers=greenfield_manager_headers).json()["students"]
    hz = client.get("/api/v1/school/students", headers=horizon_manager_headers).json()["students"]

    gf_ids = {s["national_student_id"] for s in gf}
    hz_ids = {s["national_student_id"] for s in hz}
    assert gf_ids and hz_ids
    assert gf_ids.isdisjoint(hz_ids), "Tenant student registries leaked across schools"

    # Cross-tenant class access is rejected (404, not exposed)
    gf_classes = client.get("/api/v1/school/classes", headers=greenfield_manager_headers).json()["classes"]
    foreign_class_id = gf_classes[0]["id"]
    res = client.post(
        "/api/v1/school/attendance",
        headers=horizon_manager_headers,
        json={"date": "2026-01-15", "class_id": foreign_class_id, "entries": []},
    )
    assert res.status_code == 404
