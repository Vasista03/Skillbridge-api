"""Pytest fixtures: spin up an isolated SQLite test database for each test.

Two of the tests below truly hit a real database (file-backed SQLite, not
mocks): test_full_user_journey_real_db and test_seeded_database_persists.
The rest also use a real DB but recreate it per-test for isolation.
"""

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ["DATABASE_URL"] = "sqlite:///./test_pytest.db"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-pytest"
os.environ["MONITORING_API_KEY"] = "test-monitoring-key"

from src.database import Base, get_db  # noqa: E402
from src.main import app  # noqa: E402


@pytest.fixture
def db_engine(tmp_path):
    db_path = tmp_path / "test.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_engine):
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def signup(client, role="student", email=None, name=None, institution_id=None):
    payload = {
        "name": name or f"{role.title()} Test",
        "email": email or f"{role}@test.com",
        "password": "password123",
        "role": role,
        "institution_id": institution_id,
    }
    return client.post("/auth/signup", json=payload)


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
