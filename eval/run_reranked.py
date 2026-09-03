"""Golden-set evaluation runner for the reranking experiment: retrieve()'s top-10
candidates re-scored and re-ordered by a cross-encoder, same 10 kept (not truncated
here) so MRR search depth stays comparable to the baseline. Recall@1/3/5 truncate
from this same reordered list, exactly like the baseline does.

Deliberately kept out of app/: evaluation tooling, not production retrieval code.
Reuses run_baseline.py's scoring functions unchanged, so the two runs are scored
identically and directly comparable; only the retrieval step differs.

Usage: PYTHONPATH=. uv run python -m eval.run_reranked
"""

import json
import time
from pathlib import Path

import yaml

from app.db.session import SessionLocal
from app.retrieval.reranker import rerank
from app.retrieval.service import retrieve
from eval.run_baseline import (
    GOLDEN_SET_PATH,
    SEARCH_DEPTH,
    _score_answerable_query,
    _score_unanswerable_query,
    summarize,
)

RESULTS_PATH = Path(".private/experiments/results/reranked_v1.json")


def run() -> dict:
    with open(GOLDEN_SET_PATH, encoding="utf-8") as f:
        queries = yaml.safe_load(f)

    session = SessionLocal()
    answerable_results = []
    unanswerable_results = []
    timings = []

    for query in queries:
        start = time.perf_counter()
        candidates = retrieve(query["query"], top_k=SEARCH_DEPTH, session=session)
        reranked = rerank(query["query"], candidates, top_k=SEARCH_DEPTH)
        retrieved = [rc.chunk for rc in reranked]
        elapsed = time.perf_counter() - start
        timings.append(elapsed)

        if query["expected_behavior"] == "answer":
            answerable_results.append(_score_answerable_query(query, retrieved))
        else:
            unanswerable_results.append(_score_unanswerable_query(query, retrieved))

    session.close()

    return {
        "answerable_results": answerable_results,
        "unanswerable_results": unanswerable_results,
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
