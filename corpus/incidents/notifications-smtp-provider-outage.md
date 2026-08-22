# INC-2025-0729: Delayed Order Confirmation Emails

**Severity:** SEV3

## Summary

Between 08:15 and 11:40 UTC, order confirmation emails were delayed by up to two
hours rather than being delivered within the normal window of a few minutes. SMS
delivery was not affected. No orders were lost or duplicated.

## Timeline

- 08:15 UTC: Email delivery latency begins climbing
- 08:40 UTC: On-call engineer paged after the delivery queue backlog crossed its
  alerting threshold
- 09:05 UTC: Root cause identified, confirmed as an issue on the SMTP provider's
  side rather than our own systems
- 09:10 UTC: Provider's public status page updated to acknowledge a service
  disruption
- 11:20 UTC: Provider's status page updated to resolved
- 11:40 UTC: Email delivery queue fully drained, latency back to normal

## Impact

No emails were lost, all queued emails eventually delivered. Approximately 3,100
order confirmation emails were delayed beyond the normal delivery window during the
incident.

## Root Cause

Our third-party SMTP provider experienced a service disruption on their end,
acknowledged on their public status page. Our Notifications service correctly
queued and retried failed send attempts rather than dropping them, which meant no
data loss, but the growing backlog meant new emails were delayed behind the retry
queue for the duration of the provider's disruption.

## Evidence

- Delivery queue depth metrics show a steady climb beginning at 08:15 UTC with no
  corresponding change in inbound request volume, ruling out a demand-side cause
- The SMTP provider's own status page independently confirms an incident during the
  same window
- SMS delivery, which uses a separate provider, shows no corresponding delay

## Resolution

No action was required on our side beyond continuing to retry and allowing the queue
to drain once the provider's disruption resolved. The retry and queuing behavior
worked as designed.

## Follow-up Actions

- Consider whether a secondary SMTP provider for failover is worth the added
  complexity, to be evaluated against how frequently this provider has disruptions
- Add a customer-facing order confirmation page that does not depend on email
  delivery, so confirmation isn't solely reliant on a channel outside our control
