"""Interactive demo API for the NE-EMIS dashboard.

This is a *presentation* layer only: it serves realistic in-memory data so
the UI can be explored without provisioning a PostgreSQL server. The real
integration is implemented in app/api/*, app/services/* and sql/*.

All state lives in this module for the lifetime of the process.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/demo", tags=["demo"])


def _uid(seed: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"ne-emis-demo-{seed}"))


def _iso(days_ago: int, hours: int = 0) -> str:
    return (
        datetime.now(timezone.utc) - timedelta(days=days_ago, hours=hours)
    ).isoformat()


CAMPUSES = [
    {
        "id": _uid(101),
        "code": "NGS-001",
        "name": "Unity Comprehensive College",
        "type": "secondary",
        "state": "NG-01",
        "region": "Northern Sector",
    },
    {
        "id": _uid(102),
        "code": "NGS-002",
        "name": "Bright Horizon Secondary",
        "type": "secondary",
        "state": "NG-01",
        "region": "Central Sector",
    },
    {
        "id": _uid(103),
        "code": "NGS-003",
        "name": "Green Valley TVET Centre",
        "type": "tvet",
        "state": "NG-01",
        "region": "Eastern Sector",
    },
]

STUDENTS = [
    {
        "ne_sid": "NE-SID-10000001000000000000000000000001",
        "name": "Amina Yusuf",
        "gender": "Female",
        "grade": "SS1-A",
        "status": "Active",
        "gpa": 4.62,
        "attendance_pct": 96.4,
        "truancy": 1,
        "campus": "NGS-001",
        "matriculated": "2024-09-09",
    },
    {
        "ne_sid": "NE-SID-10000001000000000000000000000002",
        "name": "Ibrahim Musa",
        "gender": "Male",
        "grade": "SS2-B",
        "status": "Active",
        "gpa": 4.10,
        "attendance_pct": 93.1,
        "truancy": 2,
        "campus": "NGS-001",
        "matriculated": "2023-09-12",
    },
    {
        "ne_sid": "NE-SID-10000001000000000000000000000003",
        "name": "Fatima Bello",
        "gender": "Female",
        "grade": "SS3-A",
        "status": "Active",
        "gpa": 4.88,
        "attendance_pct": 98.2,
        "truancy": 0,
        "campus": "NGS-002",
        "matriculated": "2023-09-12",
    },
    {
        "ne_sid": "NE-SID-10000001000000000000000000000004",
        "name": "Chinedu Okafor",
        "gender": "Male",
        "grade": "JSS3-B",
        "status": "Active",
        "gpa": 3.41,
        "attendance_pct": 89.7,
        "truancy": 6,
        "campus": "NGS-002",
        "matriculated": "2022-09-13",
    },
    {
        "ne_sid": "NE-SID-10000001000000000000000000000005",
        "name": "Mariam Abubakar",
        "gender": "Female",
        "grade": "SS1-B",
        "status": "Active",
        "gpa": 3.98,
        "attendance_pct": 94.3,
        "truancy": 3,
        "campus": "NGS-003",
        "matriculated": "2024-09-09",
    },
    {
        "ne_sid": "NE-SID-10000001000000000000000000000006",
        "name": "David Adeyemi",
        "gender": "Male",
        "grade": "SS2-A",
        "status": "Transferred",
        "gpa": 3.72,
        "attendance_pct": 91.0,
        "truancy": 4,
        "campus": "NGS-001",
        "matriculated": "2023-09-12",
    },
    {
        "ne_sid": "NE-SID-10000001000000000000000000000007",
        "name": "Halima Sani",
        "gender": "Female",
        "grade": "JSS2-A",
        "status": "Active",
        "gpa": 4.35,
        "attendance_pct": 97.0,
        "truancy": 1,
        "campus": "NGS-003",
        "matriculated": "2024-09-09",
    },
    {
        "ne_sid": "NE-SID-10000001000000000000000000000008",
        "name": "Emeka Nwosu",
        "gender": "Male",
        "grade": "SS3-B",
        "status": "Active",
        "gpa": 4.27,
        "attendance_pct": 95.6,
        "truancy": 2,
        "campus": "NGS-002",
        "matriculated": "2023-09-12",
    },
]

TEACHERS = [
    {
        "ne_tid": "NE-TID-20000001000000000000000000000001",
        "name": "Dr. Grace Adeola",
        "campus": "NGS-001",
        "subject": "Mathematics",
        "tier": 9,
        "weekly_hours": 24,
        "police_clearance": "Valid",
        "certification": "Teaching Lic. 2026",
        "status": "Active",
    },
    {
        "ne_tid": "NE-TID-20000001000000000000000000000002",
        "name": "Mr. Suleiman Danjuma",
        "campus": "NGS-001",
        "subject": "Physics",
        "tier": 8,
        "weekly_hours": 20,
        "police_clearance": "Valid",
        "certification": "Teaching Lic. 2025",
        "status": "Active",
    },
    {
        "ne_tid": "NE-TID-20000001000000000000000000000003",
        "name": "Mrs. Ngozi Eze",
        "campus": "NGS-002",
        "subject": "English",
        "tier": 7,
        "weekly_hours": 28,
        "police_clearance": "Pending Renewal",
        "certification": "Teaching Lic. 2023",
        "status": "On Leave",
    },
    {
        "ne_tid": "NE-TID-20000001000000000000000000000004",
        "name": "Mr. Abubakar Garba",
        "campus": "NGS-002",
        "subject": "Chemistry",
        "tier": 8,
        "weekly_hours": 22,
        "police_clearance": "Valid",
        "certification": "Teaching Lic. 2026",
        "status": "Active",
    },
    {
        "ne_tid": "NE-TID-20000001000000000000000000000005",
        "name": "Ms. Binta Lawal",
        "campus": "NGS-003",
        "subject": "ICT",
        "tier": 6,
        "weekly_hours": 30,
        "police_clearance": "Valid",
        "certification": "TVET Instructor Cert.",
        "status": "Active",
    },
    {
        "ne_tid": "NE-TID-20000001000000000000000000000006",
        "name": "Mr. Tunde Bakare",
        "campus": "NGS-003",
        "subject": "Technical Drawing",
        "tier": 5,
        "weekly_hours": 18,
        "police_clearance": "Expired",
        "certification": "Safety Certificate",
        "status": "Suspended",
    },
]

ATTENDANCE = [
    {"date": "2026-08-17", "present": 784, "absent": 41, "late": 19, "truant": 12},
    {"date": "2026-08-18", "present": 791, "absent": 35, "late": 22, "truant": 10},
    {"date": "2026-08-19", "present": 776, "absent": 48, "late": 18, "truant": 16},
    {"date": "2026-08-20", "present": 802, "absent": 31, "late": 17, "truant": 8},
    {"date": "2026-08-21", "present": 815, "absent": 28, "late": 15, "truant": 6},
]

LOCKS = [
    {
        "id": _uid(301),
        "entity": "payroll_entry",
        "campus": "NGS-001",
        "period": "2026-08",
        "hash": "5f5b9a1c...e0d9",
        "dean": "Dean Adeyinka (NE-MID)",
        "locked_at": _iso(1, 4),
        "status": "Locked",
    },
    {
        "id": _uid(302),
        "entity": "exam_sheet",
        "campus": "NGS-002",
        "period": "Term 2 Midterm",
        "hash": "c9c11a4b...7a21",
        "dean": "Dean Mshelia (NE-MID)",
        "locked_at": _iso(2, 1),
        "status": "Locked",
    },
    {
        "id": _uid(303),
        "entity": "attendance",
        "campus": "NGS-003",
        "period": "2026-08-19",
        "hash": "8e1ef45a...1c03",
        "dean": "Dan-Adamu Centre Lead",
        "locked_at": _iso(3),
        "status": "Locked",
    },
    {
        "id": _uid(304),
        "entity": "payroll_entry",
        "campus": "NGS-002",
        "period": "2026-07",
        "hash": "b6d0849e...4f11",
        "dean": "Dean Gwani (NE-MID)",
        "locked_at": _iso(6),
        "status": "Pending State Unlock",
    },
]

BATCHES = [
    {
        "id": "batch-2026-08-26-3",
        "batch_date": "2026-08-26",
        "phase": 3,
        "state": "Completed",
        "stats": {"students_upserted": 1248, "teachers_upserted": 96},
        "finished_at": _iso(1, 2),
    },
    {
        "id": "batch-2026-08-25-3",
        "batch_date": "2026-08-25",
        "phase": 3,
        "state": "Completed",
        "stats": {"students_upserted": 1248, "teachers_upserted": 96},
        "finished_at": _iso(2, 2),
    },
    {
        "id": "batch-2026-08-24-3",
        "batch_date": "2026-08-24",
        "phase": 3,
        "state": "Completed",
        "stats": {"students_upserted": 1241, "teachers_upserted": 95},
        "finished_at": _iso(3, 1),
    },
]

FUNDING = [
    {
        "id": _uid(401),
        "campus": "NGS-001",
        "period": "2026-08",
        "kind": "capitation",
        "amount": 3125000,
        "status": "Pending",
        "ref": "-",
    },
    {
        "id": _uid(402),
        "campus": "NGS-001",
        "period": "2026-08",
        "kind": "teacher_payroll",
        "amount": 18940000,
        "status": "Approved",
        "ref": "-",
    },
    {
        "id": _uid(403),
        "campus": "NGS-002",
        "period": "2026-08",
        "kind": "capitation",
        "amount": 2775000,
        "status": "Approved",
        "ref": "-",
    },
    {
        "id": _uid(404),
        "campus": "NGS-002",
        "period": "2026-08",
        "kind": "teacher_payroll",
        "amount": 14280000,
        "status": "Paid",
        "ref": "TRX-8841",
    },
    {
        "id": _uid(405),
        "campus": "NGS-003",
        "period": "2026-08",
        "kind": "capitation",
        "amount": 1130000,
        "status": "Paid",
        "ref": "TRX-8845",
    },
]

PAYROLL = [
    {"ne_tid": "NE-TID-...001", "name": "Dr. Grace Adeola", "campus": "NGS-001", "tier": 9, "hours": 96, "base": 1050000, "hardship": 52500, "gross": 1102500, "pension": 82688, "net": 1019813, "status": "Approved"},
    {"ne_tid": "NE-TID-...002", "name": "Mr. Suleiman Danjuma", "campus": "NGS-001", "tier": 8, "hours": 80, "base": 957000, "hardship": 47850, "gross": 1004850, "pension": 75364, "net": 929486, "status": "Approved"},
    {"ne_tid": "NE-TID-...003", "name": "Mrs. Ngozi Eze", "campus": "NGS-002", "tier": 7, "hours": 112, "base": 858000, "hardship": 0, "gross": 858000, "pension": 64350, "net": 793650, "status": "Pending"},
    {"ne_tid": "NE-TID-...004", "name": "Mr. Abubakar Garba", "campus": "NGS-002", "tier": 8, "hours": 88, "base": 957000, "hardship": 0, "gross": 957000, "pension": 71775, "net": 885225, "status": "Pending"},
    {"ne_tid": "NE-TID-...005", "name": "Ms. Binta Lawal", "campus": "NGS-003", "tier": 6, "hours": 120, "base": 767100, "hardship": 38355, "gross": 805455, "pension": 60409, "net": 745046, "status": "Approved"},
]

# Mutable demo state
_lock_state = {
    str(l["id"]): l["status"] for l in LOCKS
}
_funding_state = {
    str(f["id"]): f["status"] for f in FUNDING
}
_overview = {
    "students_total": 1248,
    "students_active": 1192,
    "new_students_this_term": 96,
    "teachers_total": 96,
    "teachers_active": 88,
    "open_vacancies": 14,
    "attendance_rate_pct": 94.8,
    "chronic_truancy": 18,
    "record_locks": len(LOCKS),
    "funding_released": 8645000,
    "funding_pending": 28370000,
    "last_aggregation": _iso(1, 2),
}


@router.get("/overview")
def overview() -> Dict[str, Any]:
    return _overview


@router.get("/campuses")
def campuses() -> List[Dict[str, Any]]:
    return CAMPUSES


@router.get("/students")
def students() -> List[Dict[str, Any]]:
    return STUDENTS


@router.get("/teachers")
def teachers() -> List[Dict[str, Any]]:
    return TEACHERS


@router.get("/attendance")
def attendance() -> List[Dict[str, Any]]:
    return ATTENDANCE


@router.get("/locks")
def locks() -> List[Dict[str, Any]]:
    return [{**l, "status": _lock_state[str(l["id"])]} for l in LOCKS]


@router.get("/batches")
def batches() -> List[Dict[str, Any]]:
    return BATCHES


@router.get("/funding")
def funding() -> List[Dict[str, Any]]:
    return [{**f, "status": _funding_state[str(f["id"])]} for f in FUNDING]


@router.get("/payroll")
def payroll() -> List[Dict[str, Any]]:
    return PAYROLL


class RunAggRequest(BaseModel):
    batch_date: date | None = None


@router.post("/aggregation/run")
def run_aggregation(body: RunAggRequest | None = None) -> Dict[str, Any]:
    d = (body.batch_date if body and body.batch_date else date.today()).isoformat()
    BATCHES.insert(
        0,
        {
            "id": f"batch-{d}-3",
            "batch_date": d,
            "phase": 3,
            "state": "Completed",
            "stats": {"students_upserted": 1248, "teachers_upserted": 96},
            "finished_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    _overview["last_aggregation"] = datetime.now(timezone.utc).isoformat()
    return {"status": "completed", "batch_id": BATCHES[0]["id"], "stats": BATCHES[0]["stats"]}


class LockAction(BaseModel):
    entity_type: str | None = None
    entity_id: str | None = None


@router.post("/locks/{lock_id}/lock")
def lock_record_action(lock_id: str, body: LockAction | None = None) -> Dict[str, Any]:
    if lock_id not in _lock_state:
        raise HTTPException(404, "Unknown lock")
    _lock_state[lock_id] = "Locked"
    return {"status": "Locked", "note": "Dean envelope signed and payload frozen"}


@router.post("/funding/{funding_id}/approve")
def approve_funding(funding_id: str) -> Dict[str, Any]:
    if funding_id not in _funding_state:
        raise HTTPException(404, "Unknown funding row")
    _funding_state[funding_id] = "Approved"
    return {"status": "Approved"}


@router.post("/funding/{funding_id}/settle")
def settle_funding(funding_id: str) -> Dict[str, Any]:
    if funding_id not in _funding_state:
        raise HTTPException(404, "Unknown funding row")
    _funding_state[funding_id] = "Paid"
    return {"status": "Paid"}


@router.post("/ingest")
def simulate_ingestion() -> Dict[str, Any]:
    _overview["last_ingestion"] = datetime.now(timezone.utc).isoformat()
    return {
        "status": "accepted",
        "accepted": 128,
        "rejected": 3,
        "message": "Phase-1 batch validated and written to campus records",
    }
