# Sift Demo Corpus Manifest

This corpus models a fictional SaaS company's engineering knowledge base, spanning
five services: Payments, Checkout, Authentication, Notifications, Analytics. It exists
to instantiate and stress-test Sift, a corpus-agnostic system; see
[docs/ROADMAP.md](../docs/ROADMAP.md) for how this fits the wider project.

The corpus is deliberately engineered with retrieval difficulty, not written to make
every query trivially answerable. This file documents that design so the reasoning
behind the corpus is visible, not just its contents.

## Hard Case 1: Near-duplicate incidents with different root causes

**Pair A: Payments gateway timeout**

Both incidents present as a Payments API "504 Gateway Timeout" with correlated
checkout failures, using near-identical opening symptom language. The discriminating
facts live in the middle of each document, not the overall gist.

| | Incident A | Incident B |
|---|---|---|
| Slug | `incidents/payments-gateway-timeout-connection-pool` | `incidents/payments-gateway-timeout-cert-expiry` |
| Root cause | A deploy reduced the DB connection pool's `max_connections` from 100 to 20; under peak load, requests queued for a connection long enough to exceed the gateway timeout | The payment processor's TLS certificate expired; outbound calls hung through a full handshake attempt instead of failing fast |
| Error code | PAY-1042 | PAY-2087 |
| Discriminator | "connection pool," "database," "recent deployment" | "certificate," "TLS," "third-party provider" |

**Pair B: Authentication login failures**

Same confusion mechanism: both present as "users can't log in." The discriminator is
the pattern of affected users, not the general symptom.

| | Incident C | Incident D |
|---|---|---|
| Slug | `incidents/auth-login-failures-rate-limiter` | `incidents/auth-login-failures-session-store` |
| Root cause | A WAF rule update throttled legitimate logins from shared corporate NAT IPs as abuse | The Redis session store hit its memory limit and evicted active sessions under LRU |
| Error code | AUTH-4401 | AUTH-5501 |
| Discriminator | Complaints cluster by corporate network | Complaints spread broadly across all users |

## Hard Case 2: Payments vs. Checkout vocabulary confusion

Checkout calls Payments (documented in `architecture/system-overview.md`), so both
services' documentation legitimately shares customer-facing vocabulary: "transaction
declined," "payment failed." The real distinguishing fact is which layer produced the
rejection.

| | Checkout-side | Payments-side |
|---|---|---|
| Slug | `runbooks/checkout-fraud-precheck-rejection` | `runbooks/payments-decline-troubleshooting` |
| Covers | Checkout's fraud-scoring step rejects the transaction before it reaches Payments | The transaction reaches Payments and is declined by the issuing bank |
| Discriminator | No corresponding Payments gateway call was ever logged | Payments gateway logs show an issuer response code |
| Error code | CHK-4400 | PAY-3011 |

## Hard Case 3: Exact error-code retrieval

Each code appears twice: a shallow one-line mention in its service doc's error
reference table, and full procedural depth in exactly one runbook or incident. Tests
whether retrieval finds the deep answer, not just any document containing the string.

| Code | Meaning | Deep answer | Shallow mention |
|---|---|---|---|
| PAY-1042 | Connection pool exhausted | Incident A | Payments service doc |
| PAY-2087 | Upstream TLS handshake failure | Incident B | Payments service doc |
| PAY-3011 | Issuer decline | Payments Decline Troubleshooting runbook | Payments service doc, FAQ |
| PAY-5090 | Null reference in charge calculation | Standalone Payments incident | Payments service doc |
| CHK-4400 | Fraud precheck rejection | Checkout Fraud Precheck runbook | Checkout service doc, FAQ |
| AUTH-4401 | Rate limit exceeded | Incident C | Authentication service doc |
| AUTH-5501 | Session not found | Incident D | Authentication service doc |
| NOTIF-3009 | SMS provider quota exceeded | Notification Delivery Failure runbook | Notifications service doc |

These codes are retrieval probes for a future experiment, not just realistic detail.
The eventual evaluation design will compare, per code, three query forms: the exact
identifier alone, the identifier plus natural-language context, and a semantically
equivalent description with no identifier at all. Documents are deliberately not
written to make any of these forms artificially easy, no keyword stuffing, no
explaining a code's meaning outside its one proper deep-answer document.

## Hard Case 4: Genuinely unanswerable questions

No document ever states that information is unavailable. Three flavors of absence:

1. **Full topic absence.** No refunds or chargebacks service or documentation exists
   anywhere in the corpus.
2. **Scope-boundary absence.** The Notifications service doc and runbook only cover
   email and SMS. Push notifications are never mentioned.
3. **Adjacent-but-not-covered absence.** The Data Retention and Access Policy exists
   and is topically relevant, but never mentions GDPR-specific deletion SLAs.

## Full document list (29)

**Service docs:** `payments`, `checkout`, `authentication`, `notifications`, `analytics`

**Runbooks:** `payments-gateway-timeout-troubleshooting`, `payments-decline-troubleshooting`,
`checkout-fraud-precheck-rejection`, `checkout-deployment-rollback`,
`auth-login-failure-triage`, `notifications-delivery-failure`,
`analytics-etl-pipeline-recovery`

**Incidents:** `payments-gateway-timeout-connection-pool`, `payments-gateway-timeout-cert-expiry`,
`auth-login-failures-rate-limiter`, `auth-login-failures-session-store`,
`payments-null-reference-error`, `checkout-frontend-deploy-bug`,
`analytics-etl-stale-data`, `notifications-smtp-provider-outage`

**Architecture:** `system-overview`, `payments-internals`, `checkout-to-analytics-data-flow`

**Deployment guides:** `standard-deployment-procedure`, `database-connection-pool-guidelines`

**Policies:** `incident-severity-classification`, `data-retention-and-access`

**FAQs:** `payments-checkout-faq`, `authentication-faq`

## Authoring notes

None of the overlap between documents is achieved through inserted repetitive
keywords or benchmark-style phrasing ("the correct answer is"). It comes from
realistic shared vocabulary, the way two real postmortems about the same service
naturally read similarly. Section headings are kept stable and descriptive (Root
Cause, Evidence, Resolution, Impact, and similar) so they double as reliable
ground-truth anchors for evaluation. Corpus authoring is kept separate from
evaluation-question authoring so the evaluation set tests retrieval rather than
reproducing phrases planted while writing the questions.
