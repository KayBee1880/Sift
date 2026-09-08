"""Golden-set evaluation runner for the fixed-size sliding-window chunking variant.

Deliberately kept out of app/: evaluation tooling, not production code, and this
variant is entirely in-memory (see eval/chunking_variants/fixed_size.py's docstring
for why). No Postgres, no persisted state, no risk to the adopted baseline
(strategy A + reranking) retrieval system.

Same golden set, same embedding model, same metric definitions (MRR, Recall@K,
all-required-coverage@K) as eval/run_baseline.py, via eval/chunking_variants/scoring.py.
The one difference from strategy A's scoring: a candidate "covers" a required/
acceptable (document, section) if its span overlaps that section, not by exact
chunk-to-section identity, since fixed-size chunks can span multiple sections.

Usage: PYTHONPATH=. uv run python -m eval.run_fixed_size_chunking
"""

import json
import time
from pathlib import Path

import numpy as np
import yaml

from app.embedding.service import embed_texts
from eval.chunking_variants.fixed_size import FixedSizeChunk, chunk_corpus_fixed_size
from eval.chunking_variants.scoring import SEARCH_DEPTH, score_answerable_query, search, summarize

GOLDEN_SET_PATH = Path("eval/golden_queries.yaml")
CORPUS_ROOT = Path("corpus")
RESULTS_PATH = Path(".private/experiments/results/fixed_size_chunking_v1.json")


def _build_index() -> tuple[list[FixedSizeChunk], np.ndarray]:
    chunks = chunk_corpus_fixed_size(CORPUS_ROOT)
    vectors = embed_texts([c.embedding_text for c in chunks])
    return chunks, np.array(vectors, dtype=np.float32)


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
