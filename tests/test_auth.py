"""Tests for signup, login, and JWT issuance.

Hits a real SQLite test database via the conftest fixtures.
"""

from jose import jwt

from src.config import settings
from tests.conftest import auth_header, signup


def test_student_signup_returns_jwt(client):
    response = signup(client, role="student", email="student1@test.com")
    assert response.status_code == 201
    body = response.json()
    assert "access_token" in body
    assert body["user"]["email"] == "student1@test.com"
    assert body["user"]["role"] == "student"

    payload = jwt.decode(body["access_token"], settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    assert payload["user_id"] == body["user"]["id"]
    assert payload["role"] == "student"
    assert "iat" in payload and "exp" in payload


def test_login_with_valid_credentials(client):
    signup(client, role="student", email="student2@test.com")
    response = client.post(
        "/auth/login",
        json={"email": "student2@test.com", "password": "password123"},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_with_invalid_password(client):
    signup(client, role="student", email="student3@test.com")
    response = client.post(
        "/auth/login",
        json={"email": "student3@test.com", "password": "wrong"},
    )
    assert response.status_code == 401


def test_signup_duplicate_email(client):
    signup(client, role="student", email="dup@test.com")
    response = signup(client, role="student", email="dup@test.com")
    assert response.status_code == 409
