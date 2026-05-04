"""Tests for attendance marking, including enrollment enforcement. Real DB."""

from src.models import BatchStudent, BatchTrainer

from tests.conftest import auth_header, signup


def _setup_session_with_student(client, db_session, enroll_student=True):
    inst = signup(client, role="institution", email="inst_a@test.com").json()
    trainer = signup(client, role="trainer", email="trainer_a@test.com").json()
    student = signup(client, role="student", email="student_a@test.com").json()

    batch = client.post(
        "/batches",
        json={"name": "Batch X", "institution_id": inst["user"]["id"]},
        headers=auth_header(inst["access_token"]),
    ).json()

    db_session.add(BatchTrainer(batch_id=batch["id"], trainer_id=trainer["user"]["id"]))
    if enroll_student:
        db_session.add(BatchStudent(batch_id=batch["id"], student_id=student["user"]["id"]))
    db_session.commit()

    session = client.post(
        "/sessions",
        json={
            "batch_id": batch["id"],
            "title": "Session 1",
            "date": "2026-05-04",
            "start_time": "10:00",
            "end_time": "11:00",
        },
        headers=auth_header(trainer["access_token"]),
    ).json()

    return student, session, batch


def test_student_marks_own_attendance(client, db_session):
    student, session, _ = _setup_session_with_student(client, db_session)
    response = client.post(
        "/attendance/mark",
        json={"session_id": session["id"], "status": "present"},
        headers=auth_header(student["access_token"]),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "present"
    assert body["student_id"] == student["user"]["id"]
    assert body["session_id"] == session["id"]


def test_unenrolled_student_cannot_mark_attendance(client, db_session):
    student, session, _ = _setup_session_with_student(client, db_session, enroll_student=False)
    response = client.post(
        "/attendance/mark",
        json={"session_id": session["id"], "status": "present"},
        headers=auth_header(student["access_token"]),
    )
    assert response.status_code == 403


def test_attendance_invalid_status_returns_422(client, db_session):
    student, session, _ = _setup_session_with_student(client, db_session)
    response = client.post(
        "/attendance/mark",
        json={"session_id": session["id"], "status": "maybe"},
        headers=auth_header(student["access_token"]),
    )
    assert response.status_code == 422


def test_attendance_nonexistent_session_returns_404(client, db_session):
    student = signup(client, role="student", email="solo@test.com").json()
    response = client.post(
        "/attendance/mark",
        json={"session_id": 9999, "status": "present"},
        headers=auth_header(student["access_token"]),
    )
    assert response.status_code == 404


def test_duplicate_attendance_updates_record(client, db_session):
    """Per AGENTS.md: choose update OR 409. We chose update."""
    student, session, _ = _setup_session_with_student(client, db_session)
    headers = auth_header(student["access_token"])
    first = client.post(
        "/attendance/mark",
        json={"session_id": session["id"], "status": "present"},
        headers=headers,
    )
    assert first.status_code == 201
    second = client.post(
        "/attendance/mark",
        json={"session_id": session["id"], "status": "late"},
        headers=headers,
    )
    assert second.status_code == 201
    assert second.json()["status"] == "late"
