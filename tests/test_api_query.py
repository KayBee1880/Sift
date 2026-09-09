from fastapi.testclient import TestClient

from app.main import app


class _FakeResponse:
    def __init__(self, content: str):
        self._content = content
        self.status_code = 200

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return {"choices": [{"message": {"content": self._content}}]}


def test_query_endpoint_returns_grounded_answer_with_citations(monkeypatch):
    monkeypatch.setattr(
        "app.generation.service.httpx.post",
        lambda *a, **k: _FakeResponse("Notifications sends messages via email and SMS [1]."),
    )

    client = TestClient(app)
    response = client.post(
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


def test_query_endpoint_empty_query_returns_422(monkeypatch):
    def _unexpected_call(*args, **kwargs):
        raise AssertionError("the model should never be called for an invalid query")

    monkeypatch.setattr("app.generation.service.httpx.post", _unexpected_call)

    client = TestClient(app)
    response = client.post("/query", json={"query": "   "})

    assert response.status_code == 422
