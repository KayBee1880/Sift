import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth.service import decode_access_token, hash_password
from app.db.models import User
from app.db.session import SessionLocal
from app.main import app

TEST_USERNAME = "test_fixtures/auth-login-user"


@pytest.fixture
def db_session():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def test_user(db_session):
    # Defensive delete first (self-healing if a previous run crashed before
    # teardown), same pattern already used for corpus-fixture isolation in
    # tests/test_ingestion_pipeline.py. A namespaced username (test_fixtures/...)
    # keeps this from ever colliding with a real seeded demo user.
    existing = db_session.execute(
        select(User).where(User.username == TEST_USERNAME)
    ).scalar_one_or_none()
    if existing is not None:
        db_session.delete(existing)
        db_session.commit()

    user = User(
        username=TEST_USERNAME,
        hashed_password=hash_password("correct-password"),
        allowed_services=["payments"],
    )
    db_session.add(user)
    db_session.commit()

    yield user

    db_session.delete(user)
    db_session.commit()


def test_login_with_correct_credentials_returns_valid_token(test_user):
    client = TestClient(app)
    response = client.post(
        "/auth/login", data={"username": TEST_USERNAME, "password": "correct-password"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert decode_access_token(body["access_token"]) == TEST_USERNAME


def test_login_with_wrong_password_returns_401(test_user):
    client = TestClient(app)
    response = client.post(
        "/auth/login", data={"username": TEST_USERNAME, "password": "wrong-password"}
    )
    assert response.status_code == 401


def test_login_with_nonexistent_username_returns_401():
    client = TestClient(app)
    response = client.post(
        "/auth/login",
        data={"username": "test_fixtures/does-not-exist", "password": "anything"},
    )
    assert response.status_code == 401


def test_login_errors_do_not_distinguish_missing_user_from_wrong_password(test_user):
    # Both failure modes must produce the exact same response, otherwise a
    # caller could enumerate valid usernames by comparing error responses.
    client = TestClient(app)
    wrong_password = client.post(
        "/auth/login", data={"username": TEST_USERNAME, "password": "wrong-password"}
    )
    no_such_user = client.post(
        "/auth/login",
        data={"username": "test_fixtures/does-not-exist", "password": "anything"},
    )
    assert wrong_password.status_code == no_such_user.status_code == 401
    assert wrong_password.json() == no_such_user.json()
