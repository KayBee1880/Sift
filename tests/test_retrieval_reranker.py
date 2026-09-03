import pytest

from app.retrieval.reranker import rerank
from app.retrieval.service import RetrievedChunk


def _chunk(chunk_id: int, document_title: str, section_anchor: str, text: str) -> RetrievedChunk:
    return RetrievedChunk(
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
        cosine_distance=0.5,
        cosine_similarity=0.5,
    )


def test_empty_candidates_returns_empty_list():
    assert rerank("some query", [], top_k=5) == []


def test_empty_query_raises():
    candidates = [_chunk(1, "Title", "Section", "some body text")]
    with pytest.raises(ValueError, match="empty or whitespace-only"):
        rerank("", candidates, top_k=5)


def test_whitespace_only_query_raises():
    candidates = [_chunk(1, "Title", "Section", "some body text")]
    with pytest.raises(ValueError, match="empty or whitespace-only"):
        rerank("   \n\t  ", candidates, top_k=5)


def test_zero_top_k_raises():
    candidates = [_chunk(1, "Title", "Section", "some body text")]
    with pytest.raises(ValueError, match="top_k must be positive"):
        rerank("query", candidates, top_k=0)


def test_negative_top_k_raises():
    candidates = [_chunk(1, "Title", "Section", "some body text")]
    with pytest.raises(ValueError, match="top_k must be positive"):
        rerank("query", candidates, top_k=-1)


def test_top_k_caps_returned_results():
    candidates = [
        _chunk(1, "Payments Gateway Timeout", "Root Cause", "The connection pool was exhausted."),
        _chunk(2, "Checkout Rollback", "Rollback Steps", "Revert the deploy and redeploy the prior build."),
        _chunk(3, "Analytics ETL Recovery", "Resolution Steps", "Re-run the failed ETL batch job."),
    ]
    result = rerank("how do I fix a connection pool exhaustion issue", candidates, top_k=2)
    assert len(result) == 2


def test_top_k_larger_than_candidates_returns_all():
    candidates = [_chunk(1, "Title", "Section", "some body text")]
    result = rerank("query", candidates, top_k=10)
    assert len(result) == 1


def test_results_sorted_descending_by_rerank_score():
    candidates = [
        _chunk(1, "Payments Gateway Timeout", "Root Cause", "The connection pool was exhausted."),
        _chunk(2, "Checkout Rollback", "Rollback Steps", "Revert the deploy and redeploy the prior build."),
        _chunk(3, "Analytics ETL Recovery", "Resolution Steps", "Re-run the failed ETL batch job."),
    ]
    result = rerank("how do I fix a connection pool exhaustion issue", candidates, top_k=3)
    scores = [rc.rerank_score for rc in result]
    assert scores == sorted(scores, reverse=True)


def test_more_relevant_candidate_scores_above_clearly_irrelevant_one():
    on_topic = _chunk(
        1,
        "Payments Gateway Timeout — Connection Pool Exhaustion",
        "Root Cause",
        "A deploy increased request volume beyond what the connection pool was sized "
        "for, causing sustained gateway timeouts during peak checkout traffic.",
    )
    off_topic = _chunk(
        2,
        "Notifications SMTP Provider Outage",
        "Root Cause",
        "The third-party SMTP provider experienced a regional outage, causing "
        "notification emails to queue and fail delivery for two hours.",
    )
    result = rerank(
        "Payments API gateway timeouts and database connection pool exhaustion, what's the cause?",
        [off_topic, on_topic],
        top_k=2,
    )
    assert result[0].chunk.chunk_id == 1


def test_repeated_call_returns_identical_order_deterministically():
    candidates = [
        _chunk(1, "Payments Gateway Timeout", "Root Cause", "The connection pool was exhausted."),
        _chunk(2, "Checkout Rollback", "Rollback Steps", "Revert the deploy and redeploy the prior build."),
        _chunk(3, "Analytics ETL Recovery", "Resolution Steps", "Re-run the failed ETL batch job."),
    ]
    first = rerank("connection pool exhaustion", candidates, top_k=3)
    second = rerank("connection pool exhaustion", candidates, top_k=3)
    assert [rc.chunk.chunk_id for rc in first] == [rc.chunk.chunk_id for rc in second]
