"""Platform upgrade suite: syllabus CRUD, RBAC attendance firewall, staff-ID
login, teacher privacy wall, role-gated media, and design/publishing controls.
"""

from __future__ import annotations

ALQALAM_TEACHER2 = "teacher2@alqalam.edu.so"
TEACH_PW = "Teach@2026"


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _login(client, email: str, password: str) -> str:
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


# --------------------------------------------------------------------------- #
# 1. Editable Syllabus Tracker — manager CRUD, teacher read-only
# --------------------------------------------------------------------------- #
def _first_class_and_subject(client, headers):
    classes = client.get("/api/v1/school/classes", headers=headers).json()["classes"]
    klass = next(c for c in classes if c["class_level"] == "Class 5")
    subjects = client.get(
        "/api/v1/school/subjects", params={"class_level": "Class 5"}, headers=headers
    ).json()["subjects"]
    subject = next(s for s in subjects if s["subject_name"] == "Mathematics")
    return klass, subject


def test_syllabus_manager_full_crud(client, greenfield_manager_headers):
    klass, subject = _first_class_and_subject(client, greenfield_manager_headers)

    created = client.post(
        "/api/v1/school/syllabus",
        json={
            "class_id": klass["id"],
            "subject_id": subject["id"],
            "term_name": "Term 1",
            "target_completion_pct": 80,
            "term_deadline": "2026-11-30",
            "topics": [
                {"title": "Fractions and decimals", "unit_code": "MAT5-01"},
                {"title": "Ratio and proportion", "unit_code": "MAT5-02"},
                {"title": "Introductory geometry", "unit_code": "MAT5-03"},
                {"title": "Data handling", "unit_code": "MAT5-04"},
            ],
        },
        headers=greenfield_manager_headers,
    )
    assert created.status_code == 201, created.text
    plan = created.json()["plan"]
    assert plan["topics_total"] == 4
    assert plan["computed_progress_pct"] == 0
    assert plan["target_completion_pct"] == 80
    plan_id = plan["id"]

    # Duplicate term for the same class subject is rejected.
    dup = client.post(
        "/api/v1/school/syllabus",
        json={"class_id": klass["id"], "subject_id": subject["id"], "term_name": "Term 1"},
        headers=greenfield_manager_headers,
    )
    assert dup.status_code == 409

    # 'Log Topic Covered' modal: tick two national curriculum units.
    topic_ids = [t["id"] for t in plan["topics"][:2]]
    logged = client.post(
        f"/api/v1/school/syllabus/{plan_id}/log-covered",
        json={"topic_ids": topic_ids, "covered": True},
        headers=greenfield_manager_headers,
    )
    assert logged.status_code == 200
    assert logged.json()["plan"]["topics_covered"] == 2
    assert logged.json()["plan"]["computed_progress_pct"] == 50

    # Manual override of the progress statistic + deadline adjustment.
    patched = client.patch(
        f"/api/v1/school/syllabus/{plan_id}",
        json={"progress_override_pct": 75, "target_completion_pct": 70, "term_deadline": "2026-12-15"},
        headers=greenfield_manager_headers,
    )
    assert patched.status_code == 200
    body = patched.json()["plan"]
    assert body["effective_progress_pct"] == 75
    assert body["on_track"] is True

    # Add + edit + delete an individual topic.
    added = client.post(
        f"/api/v1/school/syllabus/{plan_id}/topics",
        json={"title": "Revision week", "unit_code": "MAT5-05"},
        headers=greenfield_manager_headers,
    )
    assert added.status_code == 201
    new_topic_id = added.json()["topic"]["id"]
    renamed = client.patch(
        f"/api/v1/school/syllabus/topics/{new_topic_id}",
        json={"title": "Term revision & assessment", "is_covered": True},
        headers=greenfield_manager_headers,
    )
    assert renamed.status_code == 200
    assert renamed.json()["topic"]["is_covered"] is True
    assert client.delete(
        f"/api/v1/school/syllabus/topics/{new_topic_id}", headers=greenfield_manager_headers
    ).status_code == 200

    listed = client.get(
        "/api/v1/school/syllabus", params={"class_level": "Class 5"}, headers=greenfield_manager_headers
    ).json()
    assert listed["can_edit"] is True
    assert any(p["id"] == plan_id for p in listed["plans"])


def test_syllabus_teacher_is_read_only(client, greenfield_teacher_headers, greenfield_manager_headers):
    listed = client.get("/api/v1/school/syllabus", headers=greenfield_teacher_headers)
    assert listed.status_code == 200
    assert listed.json()["can_edit"] is False

    klass, subject = _first_class_and_subject(client, greenfield_manager_headers)
    blocked = client.post(
        "/api/v1/school/syllabus",
        json={"class_id": klass["id"], "subject_id": subject["id"], "term_name": "Term 2"},
        headers=greenfield_teacher_headers,
    )
    assert blocked.status_code == 403

    plans = listed.json()["plans"]
    if plans:
        plan = plans[0]
        assert client.delete(
            f"/api/v1/school/syllabus/{plan['id']}", headers=greenfield_teacher_headers
        ).status_code == 403
        if plan["topics"]:
            assert client.post(
                f"/api/v1/school/syllabus/{plan['id']}/log-covered",
                json={"topic_ids": [plan["topics"][0]["id"]], "covered": True},
                headers=greenfield_teacher_headers,
            ).status_code == 403


def test_syllabus_is_tenant_scoped(client, horizon_manager_headers, greenfield_manager_headers):
    plans = client.get("/api/v1/school/syllabus", headers=greenfield_manager_headers).json()["plans"]
    assert plans, "expected the CRUD test to have created a plan"
    foreign = client.patch(
        f"/api/v1/school/syllabus/{plans[0]['id']}",
        json={"target_completion_pct": 10},
        headers=horizon_manager_headers,
    )
    assert foreign.status_code == 404


# --------------------------------------------------------------------------- #
# 2. Staff ID + PIN authentication
# --------------------------------------------------------------------------- #
def test_staff_id_login(client, greenfield_manager_headers):
    teachers = client.get("/api/v1/school/teachers", headers=greenfield_manager_headers).json()["teachers"]
    target = next(t for t in teachers if t["email"] == ALQALAM_TEACHER2)
    staff_id = target["staff_identifier"]
    assert staff_id

    res = client.post("/api/auth/login", json={"staff_id": staff_id, "password": TEACH_PW})
    assert res.status_code == 200, res.text
    assert res.json()["user"]["role"] == "teacher"
    assert res.json()["user"]["email"] == ALQALAM_TEACHER2

    # OAuth2 form flow also routes non-email usernames through the staff path.
    form = client.post("/api/auth/token", data={"username": staff_id, "password": TEACH_PW})
    assert form.status_code == 200

    bad = client.post("/api/auth/login", json={"staff_id": staff_id, "password": "wrong-pin"})
    assert bad.status_code == 401


# --------------------------------------------------------------------------- #
# 3. Subject-restricted attendance marking engine
# --------------------------------------------------------------------------- #
def test_attendance_restricted_to_assigned_classes(client, greenfield_manager_headers):
    teacher2_token = _login(client, ALQALAM_TEACHER2, TEACH_PW)
    teacher2_headers = _headers(teacher2_token)

    schedule = client.get("/api/v1/school/my-schedule", headers=teacher2_headers).json()
    assert schedule["role"] == "teacher"
    assigned_class_ids = {p["class_id"] for p in schedule["periods"]}
    assert assigned_class_ids, "seed data should assign teacher2 a timetable"

    # Manager rebuilds the timetable: teacher2's periods in one class move to a
    # colleague, so that class must vanish from teacher2's marking authority.
    teachers = client.get("/api/v1/school/teachers", headers=greenfield_manager_headers).json()["teachers"]
    teacher2 = next(t for t in teachers if t["email"] == ALQALAM_TEACHER2)
    substitute = next(t for t in teachers if t["email"] != ALQALAM_TEACHER2 and t["is_active"])
    victim_class_id = sorted(assigned_class_ids)[-1]
    for period in schedule["periods"]:
        if period["class_id"] == victim_class_id:
            moved = client.put(
                f"/api/v1/school/classes/{victim_class_id}/subjects/{period['subject_id']}/assignment",
                json={"teacher_id": substitute["id"]},
                headers=greenfield_manager_headers,
            )
            assert moved.status_code == 200, moved.text

    refreshed = client.get("/api/v1/school/my-schedule", headers=teacher2_headers).json()
    still_assigned = {p["class_id"] for p in refreshed["periods"]}
    assert victim_class_id not in still_assigned

    # READ is blocked for the unassigned class…
    read = client.get(
        "/api/v1/school/attendance",
        params={"class_id": victim_class_id, "date": "2026-01-15"},
        headers=teacher2_headers,
    )
    assert read.status_code == 403

    # …WRITE is blocked too…
    write = client.post(
        "/api/v1/school/attendance",
        json={"date": "2026-01-15", "class_id": victim_class_id, "entries": []},
        headers=teacher2_headers,
    )
    assert write.status_code == 403

    # …while an assigned class stays fully markable.
    ok_class_id = sorted(still_assigned)[0]
    ok_read = client.get(
        "/api/v1/school/attendance",
        params={"class_id": ok_class_id, "date": "2026-01-15"},
        headers=teacher2_headers,
    )
    assert ok_read.status_code == 200

    # The manager keeps full authority over every class register.
    manager_read = client.get(
        "/api/v1/school/attendance",
        params={"class_id": victim_class_id, "date": "2026-01-15"},
        headers=greenfield_manager_headers,
    )
    assert manager_read.status_code == 200

    # Restore the original timetable so later suites see the seeded matrix.
    for period in schedule["periods"]:
        if period["class_id"] == victim_class_id:
            client.put(
                f"/api/v1/school/classes/{victim_class_id}/subjects/{period['subject_id']}/assignment",
                json={"teacher_id": teacher2["id"]},
                headers=greenfield_manager_headers,
            )


# --------------------------------------------------------------------------- #
# 4. Teacher privacy wall
# --------------------------------------------------------------------------- #
def test_teacher_cannot_read_colleague_private_records(client, greenfield_teacher_headers):
    me = client.get("/api/auth/me", headers=greenfield_teacher_headers).json()
    directory = client.get("/api/v1/school/teachers", headers=greenfield_teacher_headers).json()["teachers"]
    assert directory

    for teacher in directory:
        if teacher["id"] == me["id"]:
            # Own record stays complete.
            assert teacher.get("email") == me["email"]
            assert "restricted" not in teacher
        else:
            # Colleagues: timetable identity only — no contact/credential data.
            assert teacher.get("restricted") is True
            for private_field in ("email", "phone", "staff_identifier", "qualifications", "bio"):
                assert private_field not in teacher, f"{private_field} leaked for colleague"

    colleague = next(t for t in directory if t["id"] != me["id"])
    detail = client.get(
        f"/api/v1/school/teachers/{colleague['id']}", headers=greenfield_teacher_headers
    ).json()["teacher"]
    assert detail.get("restricted") is True
    assert "email" not in detail and "phone" not in detail


def test_manager_still_gets_full_staff_records(client, greenfield_manager_headers):
    directory = client.get("/api/v1/school/teachers", headers=greenfield_manager_headers).json()["teachers"]
    assert all("email" in t and "staff_identifier" in t for t in directory)


# --------------------------------------------------------------------------- #
# 5. Role-gated photo & media management
# --------------------------------------------------------------------------- #
PIXEL = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
    "AAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _any_student_sid(client, headers) -> str:
    groups = client.get("/api/v1/school/students/by-class", headers=headers).json()["classes"]
    for group in groups:
        if group["students"]:
            return group["students"][0]["ne_sid"]
    raise AssertionError("no students seeded")


def test_manager_uploads_student_photo(client, greenfield_manager_headers):
    sid = _any_student_sid(client, greenfield_manager_headers)
    up = client.put(
        f"/api/v1/school/students/{sid}/photo", json={"photo": PIXEL}, headers=greenfield_manager_headers
    )
    assert up.status_code == 200
    profile = client.get(f"/api/v1/school/students/{sid}", headers=greenfield_manager_headers).json()
    assert profile["student"]["photo_url"] == PIXEL if "student" in profile else profile["photo_url"] == PIXEL

    # Removal works with photo: null.
    down = client.put(
        f"/api/v1/school/students/{sid}/photo", json={"photo": None}, headers=greenfield_manager_headers
    )
    assert down.status_code == 200 and down.json()["photo_url"] is None


def test_teacher_cannot_upload_photos(client, greenfield_teacher_headers, greenfield_manager_headers):
    sid = _any_student_sid(client, greenfield_manager_headers)
    assert client.put(
        f"/api/v1/school/students/{sid}/photo", json={"photo": PIXEL}, headers=greenfield_teacher_headers
    ).status_code == 403

    teachers = client.get("/api/v1/school/teachers", headers=greenfield_manager_headers).json()["teachers"]
    assert client.put(
        f"/api/v1/school/teachers/{teachers[0]['id']}/photo",
        json={"photo": PIXEL},
        headers=greenfield_teacher_headers,
    ).status_code == 403


def test_photo_payload_must_be_an_image_data_url(client, greenfield_manager_headers):
    sid = _any_student_sid(client, greenfield_manager_headers)
    bad = client.put(
        f"/api/v1/school/students/{sid}/photo",
        json={"photo": "data:text/html;base64,PGI+"},
        headers=greenfield_manager_headers,
    )
    assert bad.status_code == 422


def test_manager_uploads_teacher_photo(client, greenfield_manager_headers):
    teachers = client.get("/api/v1/school/teachers", headers=greenfield_manager_headers).json()["teachers"]
    teacher_id = teachers[0]["id"]
    up = client.put(
        f"/api/v1/school/teachers/{teacher_id}/photo", json={"photo": PIXEL}, headers=greenfield_manager_headers
    )
    assert up.status_code == 200 and up.json()["photo_url"] == PIXEL
    client.put(
        f"/api/v1/school/teachers/{teacher_id}/photo", json={"photo": None}, headers=greenfield_manager_headers
    )


# --------------------------------------------------------------------------- #
# 6. Design system & publishing controls
# --------------------------------------------------------------------------- #
def test_ui_config_defaults_and_publish_flow(client, greenfield_manager_headers, greenfield_teacher_headers):
    initial = client.get("/api/v1/school/ui-config", headers=greenfield_teacher_headers).json()
    assert initial["config"]["accent"] == "#2563eb"
    assert initial["can_publish"] is False

    # Teachers can never push live.
    assert client.put(
        "/api/v1/school/ui-config",
        json={"accent": "#dc2626", "font": "mono", "blocks": {}},
        headers=greenfield_teacher_headers,
    ).status_code == 403

    published = client.put(
        "/api/v1/school/ui-config",
        json={"accent": "#059669", "font": "serif", "blocks": {"biometricsBadge": False}},
        headers=greenfield_manager_headers,
    )
    assert published.status_code == 200, published.text
    assert published.json()["config"]["accent"] == "#059669"

    # Every tenant session now renders the pushed design.
    live = client.get("/api/v1/school/ui-config", headers=greenfield_teacher_headers).json()
    assert live["config"]["accent"] == "#059669"
    assert live["config"]["font"] == "serif"
    assert live["config"]["blocks"]["biometricsBadge"] is False
    assert live["config"]["blocks"]["profileCard"] is True  # untouched default

    # Unknown blocks and malformed colours are rejected.
    assert client.put(
        "/api/v1/school/ui-config",
        json={"accent": "not-a-colour"},
        headers=greenfield_manager_headers,
    ).status_code == 422
    assert client.put(
        "/api/v1/school/ui-config",
        json={"blocks": {"cryptoMiner": True}},
        headers=greenfield_manager_headers,
    ).status_code == 422


def test_ui_config_is_tenant_scoped(client, horizon_manager_headers):
    other = client.get("/api/v1/school/ui-config", headers=horizon_manager_headers).json()
    assert other["config"]["accent"] == "#2563eb"  # Horizon never published a theme
