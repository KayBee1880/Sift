"""Golden-set evaluation runner for the merge-small-sections chunking variant, the
middle ground between strategy A (always one chunk per section) and fixed-size
sliding windows (section boundaries ignored entirely).

Deliberately kept out of app/ and entirely in-memory for the measurement phase,
matching the other chunking-variant runners, even though this variant (unlike
fixed-size chunking) would need no schema change to adopt for real if the numbers
support it, see eval/chunking_variants/merge_small_sections.py's docstring.

Usage: PYTHONPATH=. uv run python -m eval.run_merge_small_sections
"""

import json
import time
from pathlib import Path

import numpy as np
import yaml

from app.embedding.service import embed_texts
from eval.chunking_variants.merge_small_sections import MergedChunk, chunk_corpus_merged
from eval.chunking_variants.scoring import SEARCH_DEPTH, score_answerable_query, search, summarize

GOLDEN_SET_PATH = Path("eval/golden_queries.yaml")
CORPUS_ROOT = Path("corpus")
RESULTS_PATH = Path(".private/experiments/results/merge_small_sections_v1.json")


def _build_index() -> tuple[list[MergedChunk], np.ndarray]:
    chunks = chunk_corpus_merged(CORPUS_ROOT)
    vectors = embed_texts([c.embedding_text for c in chunks])
    return chunks, np.array(vectors, dtype=np.float32)


def run() -> dict:
    with open(GOLDEN_SET_PATH, encoding="utf-8") as f:
        queries = yaml.safe_load(f)

    print("Building in-memory merge-small-sections chunk index...")
    chunks, matrix = _build_index()
    print(f"{len(chunks)} chunks, embedding matrix shape {matrix.shape}")

    answerable_results = []
    timings = []
    for query in queries:
        if query["expected_behavior"] != "answer":
            continue
        start = time.perf_counter()
        ranked = search(query["query"], chunks, matrix, top_k=SEARCH_DEPTH)
        timings.append(time.perf_counter() - start)
        answerable_results.append(score_answerable_query(query, ranked))

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
