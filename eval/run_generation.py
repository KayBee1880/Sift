"""Golden-set evaluation runner for Sift's generation layer: every query run
through the real retrieve -> rerank -> generate_answer pipeline, with real Groq
calls, scored against expected_behavior (answer/abstain) and expected_facts.

Deliberately kept out of app/: evaluation tooling, not production code. Makes
real, metered API calls: one generation call per query, plus one LLM-judge call
per expected fact for queries that were correctly answered. Run by hand, not in
CI (see decision log, 2026-09-04, CI testing strategy).

Fact-coverage scoring uses the same Groq model as the judge, since no
meaningfully stronger free-tier alternative is available in this account's
model lineup. This is a real limitation, not a rounding error: a model judging
its own family's outputs risks being systematically lenient or making
correlated mistakes with the generator. Reported as "LLM-judged fact coverage,"
never as ground truth, and every judge verdict is saved alongside the raw
generated answer so a human can spot-check the judge itself, not just the
generator.

Also tracks latency (retrieval and generation timed separately, per Phase 3's
roadmap scope) and token usage as a "cost" proxy: Groq's free tier has no
dollar cost, so token counts against the free-tier rate limit are the
meaningful cost signal, reported separately for real query calls versus
judge calls, since a real POST /query caller never pays for the latter.

Usage: PYTHONPATH=. uv run python -m eval.run_generation
"""

import json
import time
from pathlib import Path

import yaml

from app.db.session import SessionLocal
from app.generation.service import Citation, GenerationResult, _call_groq, generate_answer
from app.retrieval.reranker import rerank
from app.retrieval.service import retrieve

GOLDEN_SET_PATH = Path("eval/golden_queries.yaml")
RESULTS_PATH = Path(".private/experiments/results/generation_v1.json")

RETRIEVAL_DEPTH = 10
GENERATION_TOP_K = 5

JUDGE_PROMPT_TEMPLATE = (
    'You are evaluating whether a generated answer supports a specific factual '
    'claim.\n\nClaim: "{fact}"\n\nGenerated answer: "{answer}"\n\n'
    "Does the generated answer state this claim, or something that clearly "
    "implies it? Respond with exactly one word, YES or NO, and nothing else."
)


def _judge_fact_supported(fact: str, answer: str) -> tuple[bool | None, int, int]:
    """Returns (verdict, prompt_tokens, completion_tokens). Verdict is True/False
    for a clear response, None if the judge's response couldn't be parsed
    unambiguously (never guessed, treated as a distinct outcome from both True and
    False in the summary, not silently coerced). Token counts are returned even for
    an unparseable verdict since the call still happened and still has a real cost
    against the free-tier rate limit, regardless of whether the answer was usable.
    """
    messages = [{"role": "user", "content": JUDGE_PROMPT_TEMPLATE.format(fact=fact, answer=answer)}]
    groq_result = _call_groq(messages)
    verdict_text = groq_result.content.strip().upper()
    if verdict_text == "YES":
        verdict = True
    elif verdict_text == "NO":
        verdict = False
    else:
        verdict = None
    return verdict, groq_result.prompt_tokens, groq_result.completion_tokens


def _citation_validity(citations: list[Citation], ground_truth: dict) -> float | None:
    """Fraction of returned citations whose document appears anywhere in the
    query's ground truth (required/acceptable/relevant_insufficient), a cheap
    structural check that doesn't need judgment. None if there were no
    citations to check (e.g. the system abstained).
    """
    if not citations:
        return None
    known_docs = {
        e["document"]
        for key in ("required", "acceptable", "relevant_insufficient")
        for e in (ground_truth.get(key) or [])
    }
    valid = sum(1 for c in citations if c.document_slug in known_docs)
    return valid / len(citations)


def _score_query(query: dict, result: GenerationResult, timings: dict) -> dict:
    expected_behavior = query["expected_behavior"]
    ground_truth = query["ground_truth"]

    entry = {
        "id": query["id"],
        "category": query["category"],
        "expected_behavior": expected_behavior,
        "actual_abstained": result.abstained,
        "answer": result.answer,
        "citations": [c.document_slug for c in result.citations],
        "citation_validity": _citation_validity(result.citations, ground_truth),
        "fact_verdicts": None,
        "fact_coverage": None,
        "correct_abstention_decision": None,
        # Real-query token usage, present even on abstention (0 for the floor case,
        # which never calls the model; real usage for the sentinel case, which does).
        "query_prompt_tokens": result.prompt_tokens,
        "query_completion_tokens": result.completion_tokens,
        # Judge-call usage, tracked separately: a real production query never
        # triggers these calls, so blending them into "query" tokens would
        # misrepresent what a live user actually costs.
        "judge_prompt_tokens": 0,
        "judge_completion_tokens": 0,
        "retrieval_seconds": timings["retrieval_seconds"],
        "generation_seconds": timings["generation_seconds"],
    }

    if expected_behavior == "abstain":
        entry["correct_abstention_decision"] = result.abstained is True
        return entry

    # expected_behavior == "answer"
    entry["correct_abstention_decision"] = result.abstained is False
    if result.abstained:
        return entry  # false abstention, nothing to judge facts against

    expected_facts = query.get("expected_facts") or []
    if expected_facts:
        judged = [_judge_fact_supported(fact, result.answer) for fact in expected_facts]
        verdicts = [v for v, _, _ in judged]
        entry["fact_verdicts"] = verdicts
        entry["judge_prompt_tokens"] = sum(p for _, p, _ in judged)
        entry["judge_completion_tokens"] = sum(c for _, _, c in judged)
        resolved = [v for v in verdicts if v is not None]
        entry["fact_coverage"] = (sum(resolved) / len(resolved)) if resolved else None

    return entry


def run() -> list[dict]:
    with open(GOLDEN_SET_PATH, encoding="utf-8") as f:
        queries = yaml.safe_load(f)

    session = SessionLocal()
    results = []
    for query in queries:
        retrieval_start = time.perf_counter()
        candidates = retrieve(query["query"], top_k=RETRIEVAL_DEPTH, session=session)
        reranked = rerank(query["query"], candidates, top_k=GENERATION_TOP_K)
        retrieval_seconds = time.perf_counter() - retrieval_start

        generation_start = time.perf_counter()
        generation_result = generate_answer(query["query"], reranked)
        generation_seconds = time.perf_counter() - generation_start

        timings = {"retrieval_seconds": retrieval_seconds, "generation_seconds": generation_seconds}
        results.append(_score_query(query, generation_result, timings))
        # Free-tier courtesy pacing across ~46 generation calls plus judge calls,
        # not a response to any specific observed rate limit.
        time.sleep(0.5)

    session.close()
    return results


def summarize(results: list[dict]) -> dict:
    abstain_queries = [r for r in results if r["expected_behavior"] == "abstain"]
    answer_queries = [r for r in results if r["expected_behavior"] == "answer"]

    abstention_accuracy = (
        sum(r["correct_abstention_decision"] for r in abstain_queries) / len(abstain_queries)
        if abstain_queries
        else None
    )
    false_abstention_rate = (
        sum(not r["correct_abstention_decision"] for r in answer_queries) / len(answer_queries)
        if answer_queries
        else None
    )

    answered_with_facts = [
        r for r in answer_queries if not r["actual_abstained"] and r["fact_coverage"] is not None
    ]
    mean_fact_coverage = (
        sum(r["fact_coverage"] for r in answered_with_facts) / len(answered_with_facts)
        if answered_with_facts
        else None
    )

    with_citations = [r for r in results if r["citation_validity"] is not None]
    mean_citation_validity = (
        sum(r["citation_validity"] for r in with_citations) / len(with_citations)
        if with_citations
        else None
    )

    def _stats(values: list[float]) -> dict:
        return {"mean": sum(values) / len(values), "min": min(values), "max": max(values)}

    # "generation_seconds" times only the answer-generation call itself, never the
    # per-fact judge calls that happen afterward in _score_query — those are
    # eval-only overhead a real POST /query caller never pays, so folding them in
    # here would overstate what a live user actually experiences.
    timing = {
        "retrieval_seconds": _stats([r["retrieval_seconds"] for r in results]),
        "generation_seconds": _stats([r["generation_seconds"] for r in results]),
        "total_seconds": _stats(
            [r["retrieval_seconds"] + r["generation_seconds"] for r in results]
        ),
    }

    # Groq's free tier has no dollar cost, so token counts against the free-tier
    # rate limit are the meaningful "cost" proxy here, not a currency amount.
    # Query tokens (what a real POST /query call pays) and judge tokens (eval-only
    # overhead, never paid by a real caller) are reported separately, not summed,
    # so this doesn't misrepresent what running the production system actually costs.
    tokens = {
        "query_prompt_tokens_total": sum(r["query_prompt_tokens"] for r in results),
        "query_completion_tokens_total": sum(r["query_completion_tokens"] for r in results),
        "judge_prompt_tokens_total": sum(r["judge_prompt_tokens"] for r in results),
        "judge_completion_tokens_total": sum(r["judge_completion_tokens"] for r in results),
    }

    return {
        "n_queries": len(results),
        "n_abstain_queries": len(abstain_queries),
        "n_answer_queries": len(answer_queries),
        "abstention_accuracy": abstention_accuracy,
        "false_abstention_rate": false_abstention_rate,
        "mean_fact_coverage_llm_judged": mean_fact_coverage,
        "mean_citation_validity": mean_citation_validity,
        "false_abstentions": [
            r["id"] for r in answer_queries if not r["correct_abstention_decision"]
        ],
        "incorrect_abstentions": [
            r["id"] for r in abstain_queries if not r["correct_abstention_decision"]
        ],
        "low_fact_coverage": [
            r["id"]
            for r in answered_with_facts
            if r["fact_coverage"] is not None and r["fact_coverage"] < 1.0
        ],
        "timing": timing,
        "tokens": tokens,
    }


if __name__ == "__main__":
    raw = run()
    summary = summarize(raw)

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump({"raw": raw, "summary": summary}, f, indent=2)

    print(json.dumps(summary, indent=2))
    print(f"\nFull results written to {RESULTS_PATH}")
