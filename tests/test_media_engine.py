"""Refinement 5 + 7/8 contracts: role-gated media engine & design system.

Covers the manager-only write gate on profile photos, payload validation,
the read-only stance for teachers, the staff-record privacy rule (a teacher
cannot open another teacher's profile), and the live design-config endpoints
behind the Publishing Control Bar.
"""

from __future__ import annotations

import base64

from app.core.db import SessionLocal
from app.models import Student, User

# A minimal valid PNG (1×1 transparent pixel) as a data URL.
_TINY_PNG = base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d494844520000000100000001080600000"
        "01f15c4890000000d49444154789c626001000000ffff03000006000557bfabd40000000049454e44ae426082"
    )
).decode()
PHOTO_URL = f"data:image/png;base64,{_TINY_PNG}"


def _login(client, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _alqalam_student_key() -> str:
    with SessionLocal() as db:
        student = (
            db.query(Student)
            .join(User, User.school_id == Student.school_id)
            .filter(User.email == "manager@alqalam.edu.so", Student.roll_number.isnot(None))
            .first()
        )
        assert student is not None
        return student.roll_number


def _alqalam_teacher_ids() -> tuple[int, int]:
    with SessionLocal() as db:
        manager_school = db.query(User).filter_by(email="manager@alqalam.edu.so").one().school_id
        teachers = (
            db.query(User)
            .filter(User.school_id == manager_school, User.role == "teacher")
            .order_by(User.id)
            .all()
        )
        assert len(teachers) >= 2
        return teachers[0].id, teachers[1].id


def _signed_in_teacher_id(client, headers) -> int:
    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200, me.text
    return me.json()["id"]


# --------------------------------------------------------------------------- #
# Student media — manager gate
# --------------------------------------------------------------------------- #
def test_manager_uploads_student_photo_and_profile_reflects_it(client):
    manager = _login(client, "manager@alqalam.edu.so", "School@2026")
    key = _alqalam_student_key()

    uploaded = client.put(
        f"/api/v1/school/media/students/{key}/photo", headers=manager, json={"photo_data": PHOTO_URL}
    )
    assert uploaded.status_code == 200, uploaded.text
    assert uploaded.json()["student"]["photo_data"] == PHOTO_URL

    profile = client.get(f"/api/v1/school/students/{key}", headers=manager)
    assert profile.status_code == 200
    assert profile.json()["photo_data"] == PHOTO_URL


def test_teacher_cannot_write_student_or_staff_media(client):
    teacher = _login(client, "teacher@alqalam.edu.so", "Teach@2026")
    key = _alqalam_student_key()
    first_teacher, _ = _alqalam_teacher_ids()

    for path in (
        f"/api/v1/school/media/students/{key}/photo",
        f"/api/v1/school/media/teachers/{first_teacher}/photo",
    ):
        put = client.put(path, headers=teacher, json={"photo_data": PHOTO_URL})
        assert put.status_code == 403, (path, put.text)
        delete = client.delete(path, headers=teacher)
        assert delete.status_code == 403, (path, delete.text)


def test_state_role_hits_the_firewall_on_media_routes(client):
    inspector = _login(client, "inspector@education.gov", "State@2026")
    key = _alqalam_student_key()
    response = client.put(
        f"/api/v1/school/media/students/{key}/photo", headers=inspector, json={"photo_data": PHOTO_URL}
    )
    assert response.status_code == 403
    assert "FIREWALL" in response.json()["detail"]


def test_photo_payload_validation(client):
    manager = _login(client, "manager@alqalam.edu.so", "School@2026")
    key = _alqalam_student_key()

    not_an_image = client.put(
        f"/api/v1/school/media/students/{key}/photo",
        headers=manager,
        json={"photo_data": "data:text/plain;base64,aGVsbG8gd29ybGQ="},
    )
    assert not_an_image.status_code == 422

    garbage = client.put(
        f"/api/v1/school/media/students/{key}/photo",
        headers=manager,
        json={"photo_data": "definitely not a data url but long enough to pass"},
    )
    assert garbage.status_code == 422

    oversized = client.put(
        f"/api/v1/school/media/students/{key}/photo",
        headers=manager,
        json={"photo_data": "data:image/png;base64," + base64.b64encode(b"x" * (513 * 1024)).decode()},
    )
    assert oversized.status_code == 413


def test_manager_uploads_and_deletes_teacher_photo(client):
    manager = _login(client, "manager@alqalam.edu.so", "School@2026")
    first_teacher, _ = _alqalam_teacher_ids()

    uploaded = client.put(
        f"/api/v1/school/media/teachers/{first_teacher}/photo",
        headers=manager,
        json={"photo_data": PHOTO_URL},
    )
    assert uploaded.status_code == 200, uploaded.text
    assert uploaded.json()["teacher"]["photo_data"] == PHOTO_URL

    removed = client.delete(
        f"/api/v1/school/media/teachers/{first_teacher}/photo", headers=manager
    )
    assert removed.status_code == 200
    assert removed.json()["teacher"]["photo_data"] is None


# --------------------------------------------------------------------------- #
# Refinement 3 — staff-record privacy between teachers
# --------------------------------------------------------------------------- #
def test_teacher_cannot_open_another_teachers_profile(client):
    teacher = _login(client, "teacher@alqalam.edu.so", "Teach@2026")
    my_id = _signed_in_teacher_id(client, teacher)
    first_teacher, second_teacher = _alqalam_teacher_ids()
    other_id = second_teacher if my_id == first_teacher else first_teacher

    blocked = client.get(f"/api/v1/school/teachers/{other_id}", headers=teacher)
    assert blocked.status_code == 403, blocked.text

    own = client.get(f"/api/v1/school/teachers/{my_id}", headers=teacher)
    assert own.status_code == 200, own.text
    assert own.json()["teacher"]["id"] == my_id


# --------------------------------------------------------------------------- #
# Refinements 7-8 — design system & publishing controls
# --------------------------------------------------------------------------- #
def test_design_config_defaults_and_manager_push_live(client):
    manager = _login(client, "manager@alqalam.edu.so", "School@2026")
    teacher = _login(client, "teacher@alqalam.edu.so", "Teach@2026")

    # Everyone in the tenant can read the live configuration.
    teacher_view = client.get("/api/v1/school/design-config", headers=teacher)
    assert teacher_view.status_code == 200
    config = teacher_view.json()["config"]
    assert config["accent"] == "#2563eb"
    assert config["font"] == "sans"
    assert all(config["blocks"].values())

    # Teachers can never publish.
    denied = client.put(
        "/api/v1/school/design-config",
        headers=teacher,
        json={"accent": "#059669", "font": "serif", "blocks": {"profileCard": False}},
    )
    assert denied.status_code == 403

    # The manager pushes a draft live; the whole tenant then reads it back.
    pushed = client.put(
        "/api/v1/school/design-config",
        headers=manager,
        json={"accent": "#059669", "font": "serif", "blocks": {"profileCard": False}},
    )
    assert pushed.status_code == 200, pushed.text
    live = pushed.json()["config"]
    assert live["accent"] == "#059669"
    assert live["font"] == "serif"
    assert live["blocks"]["profileCard"] is False
    # Unspecified toggle blocks keep their visible default.
    assert live["blocks"]["academicOverview"] is True
    assert live["published_at"]

    reread = client.get("/api/v1/school/design-config", headers=teacher).json()["config"]
    assert reread["accent"] == "#059669"
    assert reread["blocks"]["profileCard"] is False


def test_design_config_rejects_off_palette_values(client):
    manager = _login(client, "manager@alqalam.edu.so", "School@2026")

    bad_accent = client.put(
        "/api/v1/school/design-config",
        headers=manager,
        json={"accent": "#ff00aa", "font": "sans", "blocks": {}},
    )
    assert bad_accent.status_code == 422

    bad_font = client.put(
        "/api/v1/school/design-config",
        headers=manager,
        json={"accent": "#2563eb", "font": "comic", "blocks": {}},
    )
    assert bad_font.status_code == 422
