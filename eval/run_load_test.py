"""Synthetic load test for Phase 6 (measurement-driven performance work):
fires real HTTP requests at a running Sift instance and reports real latency,
throughput, cache-effectiveness, and rate-limiting numbers.

Honest framing, stated up front because this project's whole discipline is no
fabricated metrics: this is SYNTHETIC traffic, not organic production usage.
There is no real user base to measure yet, so this script is what makes
Phase 6 ("measurement-driven optimization: retrieval latency, embedding
throughput, LLM latency, caching effectiveness, concurrency, cost") possible
to do honestly without a real audience — every number it reports is real, it
is just real traffic this script generated on purpose, not traffic that
happened organically. Results should always be reported as "under synthetic
load," never implied to be a production-traffic measurement.

SAFETY: defaults to http://localhost:8000, NOT the live Render deployment.
Running this against the live URL risks reproducing the confirmed 2026-09-18
OOM incident (512MB is a genuinely tight fit for two loaded transformer
models; a burst of concurrent requests is exactly the condition that
triggered it) on the one demo link anyone else might be checking. Only point
this at the live URL deliberately, and expect it may cause a real restart.

Usage:
    uv run uvicorn app.main:app --reload   # in one terminal
    PYTHONPATH=. uv run python -m eval.run_load_test   # in another

To target the live deployment instead (accepting the OOM risk above):
    SIFT_LOAD_TEST_BASE_URL=https://sift-api-rn1a.onrender.com \
        PYTHONPATH=. uv run python -m eval.run_load_test
"""

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

BASE_URL = os.environ.get("SIFT_LOAD_TEST_BASE_URL", "http://localhost:8000")
DEMO_USERNAME = os.environ.get("SIFT_LOAD_TEST_USERNAME", "admin")
DEMO_PASSWORD = os.environ.get("SIFT_LOAD_TEST_PASSWORD", "demo-admin-pw")

RESULTS_PATH = Path(".private/experiments/results/load_test_v1.json")

# Kept small (4, not 8) so cold+warm together (8 total: cold pass runs
# these once, warm pass runs the identical 4 again) stay comfortably under
# the default rate limit (10 requests / 60s per account, see app/config.py)
# with 2 requests of headroom left for the burst pass below. An earlier,
# 8-query version of this list left no headroom at all: cold alone consumed
# 8 of the 10-request budget, so the warm pass (fired immediately after, in
# the same window) got rate-limited for 5 of its 8 requests — the two that
# got through still gave a real, correct cache-effectiveness reading, but
# off a thinner sample than intended. Confirmed live on 2026-09-21, see the
# decision log and .private/experiments/results/load_test_v1.json.
COLD_QUERIES = [
    "What channels does the Notifications service use?",
    "What is the on-call escalation policy?",
    "How is a payment refund processed?",
    "What triggers a checkout timeout?",
]
# Extra, distinct queries fired immediately after the cold+warm passes
# (8 requests already spent, 2 of the 10-request budget left) — deliberately
# intended to push this account past its remaining rate-limit budget within
# the same 60s window, a real, over-HTTP verification that the limiter built
# in Phase 4 actually engages under concurrent load, not just in the
# in-process unit tests.
BURST_QUERIES = [
    "What is the data retention policy?",
    "How are secrets rotated?",
    "What is the SLA for the Payments service?",
    "How is a failed webhook retried?",
    "What is the incident postmortem template?",
]

CONCURRENCY = 4


def _login(client: httpx.Client) -> str:
    response = client.post(
        f"{BASE_URL}/auth/login",
        data={"username": DEMO_USERNAME, "password": DEMO_PASSWORD},
    )
    response.raise_for_status()
    return response.json()["access_token"]


def _timed_query(client: httpx.Client, token: str, query: str) -> dict:
    start = time.perf_counter()
    try:
        response = client.post(
            f"{BASE_URL}/query",
            headers={"Authorization": f"Bearer {token}"},
            json={"query": query},
            timeout=60.0,
        )
        status_code = response.status_code
    except httpx.HTTPError as exc:
        status_code = None
        error = str(exc)
    else:
        error = None
    elapsed_seconds = time.perf_counter() - start
    return {
        "query": query,
        "status_code": status_code,
        "error": error,
        "elapsed_seconds": round(elapsed_seconds, 3),
    }


def _run_pass(client: httpx.Client, token: str, queries: list[str]) -> tuple[list[dict], float]:
    pass_start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        results = list(pool.map(lambda q: _timed_query(client, token, q), queries))
    wall_seconds = time.perf_counter() - pass_start
    return results, wall_seconds


def _stats(values: list[float]) -> dict | None:
    if not values:
        return None
    ordered = sorted(values)
    return {
        "mean": sum(ordered) / len(ordered),
        "p50": ordered[len(ordered) // 2],
        "p95": ordered[int(len(ordered) * 0.95)] if len(ordered) > 1 else ordered[0],
        "max": ordered[-1],
    }


def run() -> dict:
    if BASE_URL != "http://localhost:8000":
        print(f"WARNING: targeting {BASE_URL}, not localhost. See module docstring.")

    with httpx.Client() as client:
        token = _login(client)

        cold_results, cold_wall_seconds = _run_pass(client, token, COLD_QUERIES)
        # Cache TTL is 5 minutes by default (app/config.py) — the warm pass
        # runs immediately after, well within it, so a cache hit is expected,
        # not a coincidence.
        warm_results, warm_wall_seconds = _run_pass(client, token, COLD_QUERIES)
        burst_results, burst_wall_seconds = _run_pass(client, token, BURST_QUERIES)

    def _summarize_pass(results: list[dict], wall_seconds: float) -> dict:
        successes = [r for r in results if r["status_code"] == 200]
        rate_limited = [r for r in results if r["status_code"] == 429]
        other_failures = [
            r for r in results if r["status_code"] not in (200, 429)
        ]
        return {
            "n_requests": len(results),
            "n_success": len(successes),
            "n_rate_limited": len(rate_limited),
            "n_other_failures": len(other_failures),
            "other_failures": other_failures,
            "wall_seconds": round(wall_seconds, 3),
            "throughput_req_per_sec": round(len(successes) / wall_seconds, 2) if wall_seconds else None,
            "latency_seconds": _stats([r["elapsed_seconds"] for r in successes]),
        }

    cold_summary = _summarize_pass(cold_results, cold_wall_seconds)
    warm_summary = _summarize_pass(warm_results, warm_wall_seconds)
    burst_summary = _summarize_pass(burst_results, burst_wall_seconds)

    cache_speedup = None
    if cold_summary["latency_seconds"] and warm_summary["latency_seconds"]:
        cold_mean = cold_summary["latency_seconds"]["mean"]
        warm_mean = warm_summary["latency_seconds"]["mean"]
        cache_speedup = round(cold_mean / warm_mean, 1) if warm_mean else None

    return {
        "base_url": BASE_URL,
        "concurrency": CONCURRENCY,
        "cold_pass": cold_summary,
        "warm_pass": warm_summary,
        "burst_pass": burst_summary,
        "cache_speedup_x": cache_speedup,
        "raw": {"cold": cold_results, "warm": warm_results, "burst": burst_results},
    }


if __name__ == "__main__":
    summary = run()

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    printable = {k: v for k, v in summary.items() if k != "raw"}
    print(json.dumps(printable, indent=2))
    print(f"\nFull results (including raw per-request timings) written to {RESULTS_PATH}")
