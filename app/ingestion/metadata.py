# Explicit, path-keyed service ownership for every corpus v1.0 document. Deliberately
# not inferred from filename prefixes: an explicit mapping is reviewable at a glance
# and fails loudly on a missing entry, instead of silently guessing wrong for a
# document that doesn't fit an assumed naming pattern. Cross-cutting documents (no
# single owning service) map to None explicitly, not omitted.
#
# Longer-term direction: this belongs as declared metadata (the corpus manifest or
# per-document front matter stating its own service), not an external mapping that
# has to be kept in sync by hand. Not redesigning the manifest now without an
# immediate architectural need; this is a deliberate v1.0 bridge.
DOCUMENT_SERVICE: dict[str, str | None] = {
    # service_docs
    "service_docs/payments.md": "payments",
    "service_docs/checkout.md": "checkout",
    "service_docs/authentication.md": "authentication",
    "service_docs/notifications.md": "notifications",
    "service_docs/analytics.md": "analytics",
    # runbooks
    "runbooks/payments-gateway-timeout-troubleshooting.md": "payments",
    "runbooks/payments-decline-troubleshooting.md": "payments",
    "runbooks/checkout-fraud-precheck-rejection.md": "checkout",
    "runbooks/checkout-deployment-rollback.md": "checkout",
    "runbooks/auth-login-failure-triage.md": "authentication",
    "runbooks/notifications-delivery-failure.md": "notifications",
    "runbooks/analytics-etl-pipeline-recovery.md": "analytics",
    # incidents
    "incidents/payments-gateway-timeout-connection-pool.md": "payments",
    "incidents/payments-gateway-timeout-cert-expiry.md": "payments",
    "incidents/payments-null-reference-error.md": "payments",
    "incidents/auth-login-failures-rate-limiter.md": "authentication",
    "incidents/auth-login-failures-session-store.md": "authentication",
    "incidents/checkout-frontend-deploy-bug.md": "checkout",
    "incidents/analytics-etl-stale-data.md": "analytics",
    "incidents/notifications-smtp-provider-outage.md": "notifications",
    # architecture
    "architecture/system-overview.md": None,  # org-wide, spans all services
    "architecture/payments-internals.md": "payments",
    "architecture/checkout-to-analytics-data-flow.md": None,  # spans two services
    # deployment_guides
    "deployment_guides/standard-deployment-procedure.md": None,  # org-wide process
    "deployment_guides/database-connection-pool-guidelines.md": None,  # general guidance
    # policies
    "policies/incident-severity-classification.md": None,  # org-wide policy
    "policies/data-retention-and-access.md": None,  # org-wide policy
    # faqs
    "faqs/payments-checkout-faq.md": None,  # explicitly spans both services
    "faqs/authentication-faq.md": "authentication",
}


def get_service_for_source_path(source_path: str) -> str | None:
    if source_path not in DOCUMENT_SERVICE:
        raise KeyError(
            f"No service mapping declared for {source_path!r}. "
            "Add an explicit entry to DOCUMENT_SERVICE (or None for a "
            "cross-cutting document), do not guess."
        )
    return DOCUMENT_SERVICE[source_path]


def get_category_for_source_path(source_path: str) -> str:
    # category is mechanically derived from the corpus folder structure, unlike
    # service, it doesn't need an explicit mapping since the folder name is
    # unambiguous by construction.
    return source_path.split("/")[0]
