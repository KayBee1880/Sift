import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.db.models import User
from app.main import app


class _FakeResponse:
    def __init__(self, content: str):
        self._content = content
        self.status_code = 200

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return {"choices": [{"message": {"content": self._content}}]}


@pytest.fixture
def authenticated_client():
    """A TestClient with get_current_user overridden to a fixed, unrestricted
    fake user, bypassing real login/JWT machinery for tests that are about
    /query's own behavior, not authentication itself (that's covered separately
    in tests/test_api_auth.py). Cleared after each test so the override never
    leaks into a later test expecting real auth enforcement.
    """
    fake_user = User(
        id=-1, username="test-fixture-user", hashed_password="", allowed_services=None
    )
    app.dependency_overrides[get_current_user] = lambda: fake_user
    client = TestClient(app)
    yield client
    app.dependency_overrides.pop(get_current_user, None)


def test_query_endpoint_returns_grounded_answer_with_citations(monkeypatch, authenticated_client):
    monkeypatch.setattr(
        "app.generation.service.httpx.post",
        lambda *a, **k: _FakeResponse("Notifications sends messages via email and SMS [1]."),
    )

    response = authenticated_client.post(
        "/query", json={"query": "What channels does the Notifications service use?"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["abstained"] is False
    assert body["answer"] == "Notifications sends messages via email and SMS [1]."
    # Only ref [1] appears in the answer text, so only it should come back as a
    # citation, not all GENERATION_TOP_K context chunks handed to the model.
    assert len(body["citations"]) == 1
    assert all("document_slug" in c for c in body["citations"])


def test_query_endpoint_empty_query_returns_422(monkeypatch, authenticated_client):
    def _unexpected_call(*args, **kwargs):
        raise AssertionError("the model should never be called for an invalid query")

    monkeypatch.setattr("app.generation.service.httpx.post", _unexpected_call)

    response = authenticated_client.post("/query", json={"query": "   "})

    assert response.status_code == 422


def test_query_endpoint_without_auth_returns_401():
    # No dependency override, no Authorization header: real auth enforcement,
    # not bypassed by the authenticated_client fixture used elsewhere in this file.
    client = TestClient(app)
    response = client.post("/query", json={"query": "anything"})
    assert response.status_code == 401


def test_query_endpoint_passes_current_users_allowed_services_to_retrieval(monkeypatch):
    # Proves the wiring, not retrieval's filtering logic itself (that's covered
    # directly in tests/test_retrieval_service.py) — captures exactly what the
    # route passes to retrieve() for a restricted user.
    captured = {}

    def _fake_retrieve(query, top_k, session, allowed_services=None):
        captured["allowed_services"] = allowed_services
        return []

    monkeypatch.setattr("app.api.routes.query.retrieve", _fake_retrieve)

    restricted_user = User(
        id=-2, username="restricted-fixture-user", hashed_password="", allowed_services=["payments"]
    )
    app.dependency_overrides[get_current_user] = lambda: restricted_user
    try:
        client = TestClient(app)
        response = client.post("/query", json={"query": "anything"})
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    assert captured["allowed_services"] == ["payments"]
