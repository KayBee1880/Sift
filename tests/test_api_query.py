import httpx
import pytest
from fastapi.testclient import TestClient

import app.rate_limiting as rate_limiting_module
from app.auth.dependencies import get_current_user
from app.db.models import User
from app.main import app
from app.metrics import metrics

# Shared-singleton reset between tests (rate limiter, cache, metrics) lives
# in tests/conftest.py, autouse for the whole suite, not just this file.


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


def test_query_endpoint_returns_cached_answer_without_recalling_the_model(
    monkeypatch, authenticated_client
):
    call_count = {"n": 0}

    def _counting_post(*args, **kwargs):
        call_count["n"] += 1
        return _FakeResponse("Notifications sends messages via email and SMS [1].")

    monkeypatch.setattr("app.generation.service.httpx.post", _counting_post)

    first = authenticated_client.post(
        "/query", json={"query": "What channels does the Notifications service use?"}
    )
    second = authenticated_client.post(
        "/query", json={"query": "What channels does the Notifications service use?"}
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json()
    # The second call was served from cache, not a second real Groq call.
    assert call_count["n"] == 1


def test_query_endpoint_returns_429_after_exceeding_the_rate_limit(
    monkeypatch, authenticated_client
):
    monkeypatch.setattr(
        rate_limiting_module,
        "query_rate_limiter",
        rate_limiting_module.SlidingWindowRateLimiter(max_requests=1, window_seconds=60),
    )
    monkeypatch.setattr(
        "app.generation.service.httpx.post",
        lambda *a, **k: _FakeResponse("Notifications sends messages via email and SMS [1]."),
    )

    first = authenticated_client.post(
        "/query", json={"query": "What channels does the Notifications service use?"}
    )
    # A different query, so a cache hit can't be the reason this succeeds or
    # fails — this test is isolating rate-limiting behavior specifically.
    second = authenticated_client.post(
        "/query", json={"query": "What is the on-call escalation policy?"}
    )

    assert first.status_code == 200
    assert second.status_code == 429


def test_query_endpoint_increments_metrics_counters(monkeypatch, authenticated_client):
    monkeypatch.setattr(
        "app.generation.service.httpx.post",
        lambda *a, **k: _FakeResponse("INSUFFICIENT_EVIDENCE: no relevant excerpts."),
    )

    authenticated_client.post(
        "/query", json={"query": "What is the capital of a country not in this corpus?"}
    )

    snapshot = metrics.snapshot()
    assert snapshot["query.total"] == 1
    assert snapshot["query.abstained"] == 1


def test_query_endpoint_returns_503_when_groq_stays_rate_limited(monkeypatch, authenticated_client):
    # Real, confirmed under a synthetic load test (2026-09-21): 4 concurrent
    # generation calls exceeded Groq's own free-tier rate limit and stayed
    # rate-limited past _call_groq's retry budget, raising httpx.HTTPStatusError
    # unhandled — this proves it now surfaces as a clean 503, not a raw 500.
    def _always_rate_limited(*args, **kwargs):
        request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
        return httpx.Response(429, request=request)

    monkeypatch.setattr("app.generation.service.time.sleep", lambda seconds: None)
    monkeypatch.setattr("app.generation.service.httpx.post", _always_rate_limited)

    response = authenticated_client.post(
        "/query", json={"query": "What channels does the Notifications service use?"}
    )

    assert response.status_code == 503
