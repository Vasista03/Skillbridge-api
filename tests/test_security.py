"""Cross-cutting security/authorization tests. Real DB.

Includes the full end-to-end journey test that explicitly hits a real DB
without any mocks (per AGENTS.md "at least two tests must hit a real test database").
"""

from src.models import BatchStudent, BatchTrainer, User

from tests.conftest import auth_header, signup


def test_protected_endpoint_without_token_returns_401(client):
    response = client.post(
        "/batches",
        json={"name": "X", "institution_id": 1},
    )
    assert response.status_code == 401


def test_wrong_role_returns_403(client):
    student = signup(client, role="student", email="wrong_role@test.com").json()
    response = client.post(
        "/batches",
        json={"name": "X", "institution_id": 1},
        headers=auth_header(student["access_token"]),
    )
    assert response.status_code == 403


def test_invalid_token_returns_401(client):
    response = client.post(
        "/batches",
        json={"name": "X", "institution_id": 1},
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert response.status_code == 401


def test_full_user_journey_real_db(client, db_session):
    """End-to-end with a real database: signup roles, create batch, invite, join,
    create session, mark attendance, verify trainer report."""
    inst = signup(client, role="institution", email="e2e_inst@test.com").json()
    trainer = signup(client, role="trainer", email="e2e_trainer@test.com").json()
    student = signup(client, role="student", email="e2e_student@test.com").json()

    batch = client.post(
        "/batches",
        json={"name": "E2E Batch", "institution_id": inst["user"]["id"]},
        headers=auth_header(inst["access_token"]),
    ).json()

    db_session.add(BatchTrainer(batch_id=batch["id"], trainer_id=trainer["user"]["id"]))
    db_session.commit()

    invite = client.post(
        f"/batches/{batch['id']}/invite",
        headers=auth_header(trainer["access_token"]),
    ).json()

    join = client.post(
        "/batches/join",
        json={"token": invite["invite_token"]},
        headers=auth_header(student["access_token"]),
    )
    assert join.status_code == 200

    session = client.post(
        "/sessions",
        json={
            "batch_id": batch["id"],
            "title": "E2E Session",
            "date": "2026-05-10",
            "start_time": "10:00",
            "end_time": "11:00",
        },
        headers=auth_header(trainer["access_token"]),
    ).json()

    mark = client.post(
        "/attendance/mark",
        json={"session_id": session["id"], "status": "present"},
        headers=auth_header(student["access_token"]),
    )
    assert mark.status_code == 201

    report = client.get(
        f"/sessions/{session['id']}/attendance",
        headers=auth_header(trainer["access_token"]),
    )
    assert report.status_code == 200
    body = report.json()
    assert body["session_id"] == session["id"]
    assert len(body["attendance"]) == 1
    assert body["attendance"][0]["status"] == "present"


def test_seeded_database_persists(client, db_session):
    """Real DB: write users and confirm they survive the request boundary."""
    signup(client, role="student", email="persist1@test.com")
    signup(client, role="student", email="persist2@test.com")
    count = db_session.query(User).filter(User.email.like("persist%@test.com")).count()
    assert count == 2


def test_invite_one_time_use(client, db_session):
    inst = signup(client, role="institution", email="ote_inst@test.com").json()
    trainer = signup(client, role="trainer", email="ote_trainer@test.com").json()
    s1 = signup(client, role="student", email="ote_s1@test.com").json()
    s2 = signup(client, role="student", email="ote_s2@test.com").json()

    batch = client.post(
        "/batches",
        json={"name": "OTE Batch", "institution_id": inst["user"]["id"]},
        headers=auth_header(inst["access_token"]),
    ).json()
    db_session.add(BatchTrainer(batch_id=batch["id"], trainer_id=trainer["user"]["id"]))
    db_session.commit()

    invite = client.post(
        f"/batches/{batch['id']}/invite",
        headers=auth_header(trainer["access_token"]),
    ).json()

    first = client.post("/batches/join", json={"token": invite["invite_token"]}, headers=auth_header(s1["access_token"]))
    assert first.status_code == 200

    second = client.post("/batches/join", json={"token": invite["invite_token"]}, headers=auth_header(s2["access_token"]))
    assert second.status_code == 400
