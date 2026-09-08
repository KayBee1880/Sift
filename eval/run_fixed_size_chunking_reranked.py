"""Golden-set evaluation runner for fixed-size chunking + cross-encoder reranking
layered on top, testing whether the two combine or have diminishing returns.

Deliberately kept out of app/, same in-memory approach as
eval/run_fixed_size_chunking.py (see that module and
eval/chunking_variants/fixed_size.py for why). Reuses
app.retrieval.reranker's cached cross-encoder model directly rather than its
rerank() function, since rerank() is typed against RetrievedChunk's single
section_anchor field, which doesn't fit a chunk that can span multiple
sections.

Usage: PYTHONPATH=. uv run python -m eval.run_fixed_size_chunking_reranked
"""

import json
import time
from pathlib import Path

import yaml

from app.retrieval.reranker import _model as reranker_model
from eval.chunking_variants.fixed_size import FixedSizeChunk
from eval.chunking_variants.scoring import SEARCH_DEPTH, score_answerable_query, search, summarize
from eval.run_fixed_size_chunking import GOLDEN_SET_PATH, _build_index

RESULTS_PATH = Path(".private/experiments/results/fixed_size_chunking_reranked_v1.json")
RERANK_TOP_K = SEARCH_DEPTH  # keep the same depth as the un-reranked run for comparability


def _candidate_text(chunk: FixedSizeChunk) -> str:
    sections = ", ".join(chunk.overlapping_sections) if chunk.overlapping_sections else "unknown"
    return f"{chunk.document_title}\nSections: {sections}\n\n{chunk.text}"


def _rerank(query: str, candidates: list[FixedSizeChunk]) -> list[FixedSizeChunk]:
    if not candidates:
        return []
    pairs = [(query, _candidate_text(c)) for c in candidates]
    scores = reranker_model().predict(pairs)
    scored = sorted(zip(candidates, scores, strict=True), key=lambda pair: pair[1], reverse=True)
    return [chunk for chunk, _ in scored]


def run() -> dict:
    with open(GOLDEN_SET_PATH, encoding="utf-8") as f:
        queries = yaml.safe_load(f)

    print("Building in-memory fixed-size chunk index...")
    chunks, matrix = _build_index()
    print(f"{len(chunks)} chunks, embedding matrix shape {matrix.shape}")

    answerable_results = []
    timings = []
    for query in queries:
        if query["expected_behavior"] != "answer":
            continue
        start = time.perf_counter()
        candidates = search(query["query"], chunks, matrix, top_k=SEARCH_DEPTH)
        reranked = _rerank(query["query"], candidates)
        timings.append(time.perf_counter() - start)
        answerable_results.append(score_answerable_query(query, reranked))

    return {
        "n_chunks": len(chunks),
        "answerable_results": answerable_results,
        "timings_seconds": timings,
    }


if __name__ == "__main__":
    raw = run()
    summary = summarize(raw)

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump({"raw": raw, "summary": summary}, f, indent=2)

    print(json.dumps(summary, indent=2))
    print(f"\nFull results written to {RESULTS_PATH}")
