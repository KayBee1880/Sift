"""Shared in-memory search and golden-set scoring logic for chunking variants whose
chunks can cover more than one section (fixed-size windows, merged-small-section
groups, and any future variant with the same shape). Pulled out once a third variant
needed the identical logic (fixed-size, then fixed-size+reranked, now
merge-small-sections) rather than copy-pasted a third time.

Not used by strategy A's evaluation (eval/run_baseline.py): strategy A's chunks map
1:1 to a single section, so exact identity is the correct check there, this
module's overlap-based "covers" check would be strictly weaker (and wrong) to use
for it.
"""

from collections import defaultdict
from typing import Protocol

import numpy as np

from app.embedding.service import embed_query

SEARCH_DEPTH = 10
K_VALUES = [1, 3, 5]


class CoverageChunk(Protocol):
    document_slug: str
    overlapping_sections: list[str]
    embedding_text: str


def search(query: str, chunks: list[CoverageChunk], matrix: np.ndarray, top_k: int) -> list[CoverageChunk]:
    query_vector = np.array(embed_query(query), dtype=np.float32)
    # Vectors are unit-normalized (same convention as the production embedding
    # service), so cosine similarity is exactly the dot product, no separate
    # normalization step needed here.
    similarities = matrix @ query_vector
    top_indices = np.argsort(-similarities)[:top_k]
    return [chunks[i] for i in top_indices]


def chunk_covers(chunk: CoverageChunk, document: str, section: str | None) -> bool:
    if chunk.document_slug != document:
        return False
    if section is None:
        return True
    return section in chunk.overlapping_sections


def _rank_of_first_cover(
    ranked_chunks: list[CoverageChunk], answer_bearing: list[tuple[str, str | None]]
) -> int | None:
    for i, chunk in enumerate(ranked_chunks, start=1):
        if any(chunk_covers(chunk, doc, section) for doc, section in answer_bearing):
            return i
    return None


def score_answerable_query(query: dict, ranked_chunks: list[CoverageChunk]) -> dict:
    gt = query["ground_truth"]
    required = [(e["document"], e.get("section")) for e in (gt.get("required") or [])]
    acceptable = [(e["document"], e.get("section")) for e in (gt.get("acceptable") or [])]

    answer_bearing = required + acceptable
    rank = _rank_of_first_cover(ranked_chunks, answer_bearing)
    reciprocal_rank = 1.0 / rank if rank else 0.0

    recall_at_k = {}
    all_required_covered_at_k = {}
    for k in K_VALUES:
        top_k_chunks = ranked_chunks[:k]
        recall_at_k[k] = (
            sum(1 for doc, section in required if any(chunk_covers(c, doc, section) for c in top_k_chunks))
            / len(required)
            if required
            else None
        )
        all_required_covered_at_k[k] = (
            all(any(chunk_covers(c, doc, section) for c in top_k_chunks) for doc, section in required)
            if required
            else None
        )

    return {
        "id": query["id"],
        "category": query["category"],
        "rank_of_first_answer_bearing": rank,
        "reciprocal_rank": reciprocal_rank,
        "recall_at_k": recall_at_k,
        "all_required_covered_at_k": all_required_covered_at_k,
    }


def summarize(raw: dict) -> dict:
    answerable = raw["answerable_results"]

    def mean(values):
        values = [v for v in values if v is not None]
        return sum(values) / len(values) if values else None

    overall = {
        "mrr": mean([r["reciprocal_rank"] for r in answerable]),
        **{f"recall_at_{k}": mean([r["recall_at_k"][k] for r in answerable]) for k in K_VALUES},
        "n_queries": len(answerable),
    }

    by_category = defaultdict(list)
    for r in answerable:
        by_category[r["category"]].append(r)
    category_summary = {
        cat: {
            "mrr": mean([r["reciprocal_rank"] for r in rows]),
            **{f"recall_at_{k}": mean([r["recall_at_k"][k] for r in rows]) for k in K_VALUES},
            "n_queries": len(rows),
        }
        for cat, rows in by_category.items()
    }

    multi_doc = [r for r in answerable if r["category"] == "multi_document"]
    multi_doc_summary = {
        f"all_required_covered_at_{k}": mean([r["all_required_covered_at_k"][k] for r in multi_doc])
        for k in K_VALUES
    }

    return {
        "n_chunks": raw["n_chunks"],
        "overall": overall,
        "by_category": category_summary,
        "multi_document_coverage": multi_doc_summary,
        "timing": {
            "mean_seconds": sum(raw["timings_seconds"]) / len(raw["timings_seconds"]),
            "max_seconds": max(raw["timings_seconds"]),
            "min_seconds": min(raw["timings_seconds"]),
        },
    }
