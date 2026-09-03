from dataclasses import dataclass
from functools import lru_cache

from sentence_transformers import CrossEncoder

from app.retrieval.service import RetrievedChunk

# Standard, well-tested open cross-encoder baseline for passage reranking. Small
# enough to run on CPU at the candidate-pool sizes used here (top 10 per query).
RERANKER_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"


@dataclass
class RerankedChunk:
    chunk: RetrievedChunk
    rerank_score: float


@lru_cache
def _model() -> CrossEncoder:
    return CrossEncoder(RERANKER_MODEL_NAME)


def _candidate_text(chunk: RetrievedChunk) -> str:
    # Deliberately mirrors the bi-encoder's embedding-text header (document title +
    # section), not just the raw chunk body: HC1's near-duplicate incidents have
    # sections that read similarly to each other in isolation (that's the whole
    # point of the hard case), so the cross-encoder needs the same provenance signal
    # a real caller already has via RetrievedChunk to have any chance of telling them
    # apart, rather than being handed the exact same underspecified text that
    # produced the confusion in the first place.
    return f"{chunk.document_title}\nSection: {chunk.section_anchor}\n\n{chunk.text}"


def rerank(query: str, candidates: list[RetrievedChunk], top_k: int) -> list[RerankedChunk]:
    """Re-score and re-order a candidate pool from retrieve() using a cross-encoder.

    Unlike the bi-encoder, the cross-encoder scores each (query, candidate) pair
    jointly rather than comparing independently-computed vectors, which is the
    specific property expected to help distinguish near-duplicate documents. Scores
    are raw model logits, not calibrated probabilities, higher means more relevant;
    they are meaningful only for ordering candidates within one query's pool, not for
    comparison across queries or against cosine distance/similarity.
    """
    if not query or not query.strip():
        raise ValueError("rerank: query is empty or whitespace-only")
    if top_k <= 0:
        raise ValueError(f"rerank: top_k must be positive, got {top_k}")
    if not candidates:
        return []

    pairs = [(query, _candidate_text(c)) for c in candidates]
    scores = _model().predict(pairs)

    reranked = sorted(
        (RerankedChunk(chunk=c, rerank_score=float(s)) for c, s in zip(candidates, scores, strict=True)),
        key=lambda rc: rc.rerank_score,
        reverse=True,
    )
    return reranked[:top_k]
