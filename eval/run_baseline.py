"""Golden-set evaluation runner for Sift's baseline exact dense retrieval.

Deliberately kept out of app/, this is evaluation tooling, not production retrieval
code. It calls app.retrieval.service.retrieve as a black box and scores results
against eval/golden_queries.yaml.

Usage: PYTHONPATH=. uv run python eval/run_baseline.py
"""

import json
import time
from collections import defaultdict
from pathlib import Path

import yaml

from app.db.session import SessionLocal
from app.retrieval.service import retrieve

GOLDEN_SET_PATH = Path("eval/golden_queries.yaml")
RESULTS_PATH = Path(".private/experiments/results/baseline_dense_v1.json")

# MRR needs to find the rank of the first answer-bearing result, which may fall
# beyond the largest K we report Recall@K for. Retrieving a generous common depth
# once per query and truncating it for each K keeps Recall@1/3/5 as strict subsets
# of the same ranked list MRR uses, rather than re-querying per K.
SEARCH_DEPTH = 10
K_VALUES = [1, 3, 5]


def _evidence_key(entry: dict) -> tuple[str, str | None]:
    return (entry["document"], entry.get("section"))


def _chunk_key(chunk) -> tuple[str, str]:
    return (chunk.document_slug, chunk.section_anchor)


def _score_answerable_query(query: dict, retrieved: list) -> dict:
    gt = query["ground_truth"]
    required = [_evidence_key(e) for e in (gt.get("required") or [])]
    acceptable = [_evidence_key(e) for e in (gt.get("acceptable") or [])]
    distractor_docs = {e["document"] for e in (gt.get("known_distractors") or [])}

    # Resolution to the required/acceptable scoring ambiguity flagged before
    # implementation: Recall@K counts ONLY literal `required` entries, since the
    # schema does not structurally record which specific required entry (when a
    # query has more than one) a given `acceptable` entry substitutes for. MRR, per
    # the explicitly confirmed rule, treats required UNION acceptable as
    # answer-bearing. Acceptable-hit coverage is tracked as its own separate
    # diagnostic signal, never folded into the Recall@K numerator or denominator.
    answer_bearing_keys = set(required) | set(acceptable)
    ranked_keys = [_chunk_key(c) for c in retrieved]

    rank = next((i for i, k in enumerate(ranked_keys, start=1) if k in answer_bearing_keys), None)
    reciprocal_rank = 1.0 / rank if rank else 0.0

    recall_at_k = {}
    all_required_covered_at_k = {}
    acceptable_hit_at_k = {}
    for k in K_VALUES:
        top_k = set(ranked_keys[:k])
        recall_at_k[k] = (sum(1 for r in required if r in top_k) / len(required)) if required else None
        all_required_covered_at_k[k] = all(r in top_k for r in required) if required else None
        acceptable_hit_at_k[k] = any(a in top_k for a in acceptable) if acceptable else False

    distractor_hit_at_5 = [c.document_slug for c in retrieved[:5] if c.document_slug in distractor_docs]

    return {
        "id": query["id"],
        "category": query["category"],
        "hard_case": query.get("hard_case"),
        "query_form": query.get("query_form"),
        "rank_of_first_answer_bearing": rank,
        "reciprocal_rank": reciprocal_rank,
        "recall_at_k": recall_at_k,
        "all_required_covered_at_k": all_required_covered_at_k,
        "acceptable_hit_at_k": acceptable_hit_at_k,
        "distractor_hit_at_5": distractor_hit_at_5,
        "required": required,
        "acceptable": acceptable,
        "retrieved_top5": [
            {
                "document_slug": c.document_slug,
                "section_anchor": c.section_anchor,
                "cosine_distance": round(c.cosine_distance, 4),
            }
            for c in retrieved[:5]
        ],
    }


def _score_unanswerable_query(query: dict, retrieved: list) -> dict:
    gt = query["ground_truth"]
    relevant_insufficient_docs = {e["document"] for e in (gt.get("relevant_insufficient") or [])}
    hit_relevant_insufficient = [
        c.document_slug for c in retrieved[:5] if c.document_slug in relevant_insufficient_docs
    ]
    return {
        "id": query["id"],
        "hard_case": query.get("hard_case"),
        "retrieved_top5": [
            {
                "document_slug": c.document_slug,
                "section_anchor": c.section_anchor,
                "cosine_distance": round(c.cosine_distance, 4),
            }
            for c in retrieved[:5]
        ],
        "relevant_insufficient_hit": hit_relevant_insufficient,
    }


def run() -> dict:
    with open(GOLDEN_SET_PATH, encoding="utf-8") as f:
        queries = yaml.safe_load(f)

    session = SessionLocal()
    answerable_results = []
    unanswerable_results = []
    timings = []

    for query in queries:
        start = time.perf_counter()
        retrieved = retrieve(query["query"], top_k=SEARCH_DEPTH, session=session)
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
    category_summary = {}
    for cat, rows in by_category.items():
        category_summary[cat] = {
            "mrr": mean([r["reciprocal_rank"] for r in rows]),
            **{f"recall_at_{k}": mean([r["recall_at_k"][k] for r in rows]) for k in K_VALUES},
            "n_queries": len(rows),
        }

    by_form = defaultdict(list)
    for r in answerable:
        if r["category"] == "exact_code":
            by_form[r["query_form"]].append(r)
    form_summary = {}
    for form, rows in by_form.items():
        form_summary[form] = {
            "mrr": mean([r["reciprocal_rank"] for r in rows]),
            **{f"recall_at_{k}": mean([r["recall_at_k"][k] for r in rows]) for k in K_VALUES},
            "n_queries": len(rows),
        }

    multi_doc = [r for r in answerable if r["category"] == "multi_document"]
    multi_doc_summary = {
        f"all_required_covered_at_{k}": mean([r["all_required_covered_at_k"][k] for r in multi_doc])
        for k in K_VALUES
    }

    failures_at_5 = [
        r for r in answerable if r["recall_at_k"][5] is not None and r["recall_at_k"][5] < 1.0
    ]

    return {
        "overall": overall,
        "by_category": category_summary,
        "hc3_by_query_form": form_summary,
        "multi_document_coverage": multi_doc_summary,
        "failures_at_k5": failures_at_5,
        "n_failures_at_k5": len(failures_at_5),
        "timing": {
            "mean_seconds": sum(raw["timings_seconds"]) / len(raw["timings_seconds"]),
            "max_seconds": max(raw["timings_seconds"]),
            "min_seconds": min(raw["timings_seconds"]),
        },
    }


if __name__ == "__main__":
    raw = run()
    summary = summarize(raw)

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump({"raw": raw, "summary": summary}, f, indent=2)

    print(json.dumps(summary, indent=2))
    print(f"\nFull results written to {RESULTS_PATH}")
