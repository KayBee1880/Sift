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
failure handling, caching and rate limiting (only where measurement justifies them).

### Phase 5 — Deployment & Observability

Cloud deployment (free-tier infrastructure), structured logging, metrics, tracing,
health checks.

### Phase 6 — Performance Optimization

Measurement-driven optimization: retrieval latency, embedding throughput, LLM latency,
caching effectiveness, concurrency, cost.

## How Scope Changes

This roadmap will evolve. When it does, the change is documented with the problem that
justified it — not added because a technology "looks impressive." Phase boundaries are
guidelines, not contracts; if evidence from an earlier phase suggests reordering later
work, that reasoning is recorded rather than silently changing the plan.
