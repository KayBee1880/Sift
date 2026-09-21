# Sift — Roadmap & Scope

## Vision

Sift is a production-oriented, corpus-agnostic **enterprise knowledge intelligence
platform**: it helps engineering teams retrieve and synthesize grounded, cited answers
from their internal technical documentation (runbooks, incident postmortems,
architecture docs, deployment guides), instead of manually searching across scattered
files.

Sift is built and evaluated against a demo/evaluation corpus modeled on a fictional SaaS
company's engineering knowledge base (five services: Payments, Checkout, Authentication,
Notifications, Analytics). That corpus is an illustrative dataset used to instantiate and
stress-test the system — it is not the boundary of what Sift is designed to do. Nothing
in the architecture is intended to assume a specific company's structure.

This project is being built as a **flagship portfolio piece**, developed in explicit,
evidence-driven phases. Each phase is scoped deliberately rather than added for
resume-keyword reasons — every phase exists because a specific engineering problem
justified it.

## Phased Build Plan

### Phase 1 — Baseline RAG (MVP)

The smallest credible end-to-end system, anchored on a single user journey: an on-call
engineer investigating a production incident.

**In scope:**
- Ingestion pipeline for the demo corpus (~28-30 documents): parsing, normalization,
  chunking
- Local, open-source embedding generation (sentence-transformers)
- PostgreSQL + pgvector for chunk/metadata/vector storage
- `POST /query` API: query embedding → semantic top-k retrieval → context construction
  → grounded generation (Groq-hosted open model) → cited answer
- Explicit insufficient-evidence abstention — the system says "I don't know" when
  retrieved evidence is weak, rather than guessing
- A hand-labeled golden evaluation set (~40 queries) with a Recall@K / MRR baseline —
  established before any retrieval-improvement claim is made
- Docker Compose local dev environment, pytest coverage for deterministic components,
  and CI (GitHub Actions) from the first commit

**Explicit non-goals for Phase 1** (deferred, not forgotten):
- Hybrid/lexical retrieval, reranking → Phase 2
- Auth, authorization, document-level permissions, prompt-injection defenses, caching,
  rate limiting → Phase 4
- Cloud deployment, monitoring/observability → Phase 5
- Document versioning / staleness handling → Phase 2+

### Phase 2 — Retrieval Engineering

Improve retrieval using the Phase 1 baseline as the control. Candidate experiments:
metadata filtering, lexical/full-text search, hybrid retrieval, reranking, chunking
strategy variations (size/overlap), query processing. Every change is measured against
the same golden evaluation set used in Phase 1 — improvements are only claimed when the
numbers support them.

### Phase 3 — Evaluation as a First-Class Subsystem

Formalizes evaluation beyond the Phase 1 baseline: generation-quality metrics
(groundedness, faithfulness, citation correctness, answer relevance), latency/throughput/
cost measurement, and a more systematic evaluation harness.

### Phase 4 — Reliability & Security

Introduced once the system is capable enough to need it: authentication/authorization,
document-level access control, prompt-injection defenses, data-leakage prevention,
failure handling, caching and rate limiting.

Real JWT auth and per-service access control (enforced at the retrieval SQL boundary,
not post-hoc) and adversarial prompt-injection testing (two real vulnerabilities found
and fixed) shipped first. Rate limiting and caching followed once the deployed system
had a concrete, non-hypothetical reason to need them: a live, public URL sharing one
free-tier Groq API quota, not a projected future traffic pattern. A sliding-window
limiter and an in-memory TTL cache, both scoped to this project's single-instance
deployment (a multi-instance rollout would need a shared store instead).

### Phase 5 — Deployment & Observability

Cloud deployment (free-tier infrastructure), structured logging, metrics, tracing,
health checks.

Live on Neon + Render. Structured JSON request logging was built in direct response to
a real, confirmed out-of-memory incident, not speculatively. A `/health` endpoint and a
`/metrics` JSON counter snapshot cover the rest of this phase's scope at a level
proportionate to this project's actual scale — Prometheus/Grafana/OpenTelemetry-grade
tracing infrastructure was deliberately not built, since there is still no measured
traffic volume that would justify operating it.

### Phase 6 — Performance Optimization

Measurement-driven optimization: retrieval latency, embedding throughput, LLM latency,
caching effectiveness, concurrency, cost.

With no organic user traffic to measure yet, this phase is driven by a disclosed
synthetic load-testing harness (`eval/run_load_test.py`) instead: real HTTP requests,
fired deliberately rather than by real users, measuring real latency, throughput, and
cache-effectiveness numbers against a running instance. Reported honestly as synthetic
load throughout, never implied to be an organic-traffic measurement.

## How Scope Changes

This roadmap will evolve. When it does, the change is documented with the problem that
justified it — not added because a technology "looks impressive." Phase boundaries are
guidelines, not contracts; if evidence from an earlier phase suggests reordering later
work, that reasoning is recorded rather than silently changing the plan.
