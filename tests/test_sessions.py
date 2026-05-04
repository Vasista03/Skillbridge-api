"""Tests for trainer creating sessions. Real DB."""

from src.database import get_db
from src.models import BatchTrainer

from tests.conftest import auth_header, signup


def _setup_trainer_and_batch(client, db_session):
    inst = signup(client, role="institution", email="inst1@test.com").json()
    inst_token = inst["access_token"]

    trainer = signup(client, role="trainer", email="trainer1@test.com").json()
    trainer_token = trainer["access_token"]

    batch_resp = client.post(
        "/batches",
        json={"name": "Batch 1", "institution_id": inst["user"]["id"]},
        headers=auth_header(inst_token),
    )
    assert batch_resp.status_code == 201
    batch = batch_resp.json()

    db_session.add(BatchTrainer(batch_id=batch["id"], trainer_id=trainer["user"]["id"]))
    db_session.commit()

    return trainer, trainer_token, batch


def test_trainer_creates_session(client, db_session):
    trainer, token, batch = _setup_trainer_and_batch(client, db_session)
    response = client.post(
        "/sessions",
        json={
            "batch_id": batch["id"],
            "title": "Python Basics",
            "date": "2026-05-04",
            "start_time": "10:00",
            "end_time": "11:00",
        },
        headers=auth_header(token),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Python Basics"
    assert body["batch_id"] == batch["id"]
    assert body["trainer_id"] == trainer["user"]["id"]


def test_session_creation_missing_fields_returns_422(client, db_session):
    _, token, batch = _setup_trainer_and_batch(client, db_session)
    response = client.post(
        "/sessions",
        json={"batch_id": batch["id"], "title": "Incomplete"},
        headers=auth_header(token),
    )
    assert response.status_code == 422


def test_session_creation_invalid_batch_returns_404(client, db_session):
    _, token, _ = _setup_trainer_and_batch(client, db_session)
    response = client.post(
        "/sessions",
        json={
            "batch_id": 9999,
            "title": "Ghost",
            "date": "2026-05-04",
            "start_time": "10:00",
            "end_time": "11:00",
        },
        headers=auth_header(token),
    )
    assert response.status_code == 404


def test_session_creation_wrong_role_returns_403(client):
    student = signup(client, role="student", email="s_sess@test.com").json()
    response = client.post(
        "/sessions",
        json={
            "batch_id": 1,
            "title": "X",
            "date": "2026-05-04",
            "start_time": "10:00",
            "end_time": "11:00",
        },
        headers=auth_header(student["access_token"]),
    )
    assert response.status_code == 403
