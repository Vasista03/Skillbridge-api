"""Tests for the monitoring endpoint and its dual-token requirement. Real DB."""

from src.config import settings

from tests.conftest import auth_header, signup


def _get_monitoring_token(client):
    monitor = signup(client, role="monitoring_officer", email="m@test.com").json()
    resp = client.post(
        "/auth/monitoring-token",
        json={"key": settings.MONITORING_API_KEY},
        headers=auth_header(monitor["access_token"]),
    )
    assert resp.status_code == 200
    return monitor, resp.json()["access_token"]


def test_post_monitoring_attendance_returns_405(client):
    response = client.post("/monitoring/attendance")
    assert response.status_code == 405


def test_monitoring_attendance_requires_scoped_token(client):
    monitor = signup(client, role="monitoring_officer", email="m2@test.com").json()
    response = client.get(
        "/monitoring/attendance",
        headers=auth_header(monitor["access_token"]),
    )
    assert response.status_code == 401


def test_monitoring_attendance_with_scoped_token(client):
    _, scoped = _get_monitoring_token(client)
    response = client.get("/monitoring/attendance", headers=auth_header(scoped))
    assert response.status_code == 200
    body = response.json()
    assert "total_records" in body
    assert "records" in body


def test_monitoring_token_requires_correct_key(client):
    monitor = signup(client, role="monitoring_officer", email="m3@test.com").json()
    response = client.post(
        "/auth/monitoring-token",
        json={"key": "wrong-key"},
        headers=auth_header(monitor["access_token"]),
    )
    assert response.status_code == 401


def test_non_monitoring_role_cannot_get_monitoring_token(client):
    student = signup(client, role="student", email="not_monitor@test.com").json()
    response = client.post(
        "/auth/monitoring-token",
        json={"key": settings.MONITORING_API_KEY},
        headers=auth_header(student["access_token"]),
    )
    assert response.status_code == 403
