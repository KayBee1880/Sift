import pytest

from app.generation.service import (
    MIN_RETRIEVAL_SIMILARITY,
    MODEL_ABSTENTION_SENTINEL,
    build_context,
    build_messages,
    generate_answer,
)
from app.retrieval.reranker import RerankedChunk
from app.retrieval.service import RetrievedChunk


def _reranked_chunk(
    chunk_id: int,
    document_title: str,
    section_anchor: str,
    text: str,
    cosine_similarity: float = 0.8,
) -> RerankedChunk:
    chunk = RetrievedChunk(
        chunk_id=chunk_id,
        document_id=chunk_id,
        document_slug=f"doc-{chunk_id}",
        source_path=f"doc-{chunk_id}.md",
        document_title=document_title,
        service=None,
        category="test",
        section_anchor=section_anchor,
        section_index=0,
        section_chunk_index=0,
        text=text,
        cosine_distance=1.0 - cosine_similarity,
        cosine_similarity=cosine_similarity,
    )
    return RerankedChunk(chunk=chunk, rerank_score=1.0)


class _FakeResponse:
    def __init__(self, content: str):
        self._content = content
        self.status_code = 200

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return {"choices": [{"message": {"content": self._content}}]}


def test_build_context_numbers_chunks_and_matches_citations():
    chunks = [
        _reranked_chunk(1, "Payments Gateway Timeout", "Root Cause", "The pool was exhausted."),
        _reranked_chunk(2, "Checkout Rollback", "Rollback Steps", "Revert the deploy."),
    ]
    context, citations = build_context(chunks)

    assert "[1] Payments Gateway Timeout — Root Cause" in context
    assert "[2] Checkout Rollback — Rollback Steps" in context
    assert "The pool was exhausted." in context
    assert [c.ref for c in citations] == [1, 2]
    assert citations[0].document_slug == "doc-1"
    assert citations[1].section_anchor == "Rollback Steps"


def test_build_context_empty_chunks_produces_empty_context_and_citations():
    context, citations = build_context([])
    assert context == ""
    assert citations == []


def test_build_messages_includes_sentinel_instruction_and_query():
    messages = build_messages("how do I fix X", "[1] some context")
    assert messages[0]["role"] == "system"
    assert MODEL_ABSTENTION_SENTINEL in messages[0]["content"]
    assert messages[1]["role"] == "user"
    assert "how do I fix X" in messages[1]["content"]
    assert "[1] some context" in messages[1]["content"]


def test_generate_answer_empty_query_raises():
    with pytest.raises(ValueError, match="empty or whitespace-only"):
        generate_answer("", [_reranked_chunk(1, "Title", "Section", "text")])


def test_generate_answer_no_chunks_abstains_without_calling_model(monkeypatch):
    def _unexpected_call(*args, **kwargs):
        raise AssertionError("httpx.post should not be called when there are no candidates")

    monkeypatch.setattr("app.generation.service.httpx.post", _unexpected_call)

    result = generate_answer("some query", [])
    assert result.abstained is True
    assert result.citations == []


def test_generate_answer_low_similarity_abstains_without_calling_model(monkeypatch):
    def _unexpected_call(*args, **kwargs):
        raise AssertionError("httpx.post should not be called below the similarity floor")

    monkeypatch.setattr("app.generation.service.httpx.post", _unexpected_call)

    weak_chunk = _reranked_chunk(
        1, "Unrelated Doc", "Section", "irrelevant text", cosine_similarity=MIN_RETRIEVAL_SIMILARITY - 0.01
    )
    result = generate_answer("some query", [weak_chunk])
    assert result.abstained is True
    assert result.citations == []


def test_generate_answer_returns_grounded_answer_with_citations(monkeypatch):
    monkeypatch.setattr(
        "app.generation.service.httpx.post",
        lambda *a, **k: _FakeResponse("Notifications sends email and SMS [1]."),
    )

    chunks = [_reranked_chunk(1, "Notifications Overview", "Overview", "Sends via email and SMS.")]
    result = generate_answer("what channels does notifications use", chunks)

    assert result.abstained is False
    assert result.answer == "Notifications sends email and SMS [1]."
    assert len(result.citations) == 1
    assert result.citations[0].document_slug == "doc-1"


def test_generate_answer_detects_model_abstention_sentinel(monkeypatch):
    monkeypatch.setattr(
        "app.generation.service.httpx.post",
        lambda *a, **k: _FakeResponse(
            f"{MODEL_ABSTENTION_SENTINEL} The excerpts only cover email and SMS, not push notifications."
        ),
    )

    chunks = [_reranked_chunk(1, "Notifications Overview", "Overview", "Sends via email and SMS.")]
    result = generate_answer("does notifications support push", chunks)

    assert result.abstained is True
    assert result.citations == []
    assert "push notifications" in result.answer


class _FakeRateLimitedResponse:
    def __init__(self):
        self.status_code = 429

    def raise_for_status(self):
        raise RuntimeError("429 rate limited")


def test_generate_answer_retries_on_rate_limit_then_succeeds(monkeypatch):
    monkeypatch.setattr("app.generation.service.time.sleep", lambda seconds: None)

    call_count = {"n": 0}

    def _flaky_post(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] < 3:
            return _FakeRateLimitedResponse()
        return _FakeResponse("Notifications sends email and SMS [1].")

    monkeypatch.setattr("app.generation.service.httpx.post", _flaky_post)

    chunks = [_reranked_chunk(1, "Notifications Overview", "Overview", "Sends via email and SMS.")]
    result = generate_answer("what channels does notifications use", chunks)

    assert call_count["n"] == 3
    assert result.abstained is False
    assert result.answer == "Notifications sends email and SMS [1]."


def test_generate_answer_gives_up_after_max_retries_on_persistent_rate_limit(monkeypatch):
    from app.generation.service import GROQ_MAX_RETRIES

    monkeypatch.setattr("app.generation.service.time.sleep", lambda seconds: None)

    call_count = {"n": 0}

    def _always_rate_limited(*args, **kwargs):
        call_count["n"] += 1
        return _FakeRateLimitedResponse()

    monkeypatch.setattr("app.generation.service.httpx.post", _always_rate_limited)

    chunks = [_reranked_chunk(1, "Notifications Overview", "Overview", "Sends via email and SMS.")]
    with pytest.raises(RuntimeError, match="429 rate limited"):
        generate_answer("what channels does notifications use", chunks)

    assert call_count["n"] == GROQ_MAX_RETRIES
