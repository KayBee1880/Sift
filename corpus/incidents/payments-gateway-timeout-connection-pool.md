# INC-2024-0512: Payments API Gateway Timeout

**Severity:** SEV2

## Summary

Between 14:12 and 15:47 UTC, the Payments API returned intermittent 504 Gateway
Timeout responses, with error rates peaking at 18% of all charge requests. Checkout
reported a corresponding spike in failed orders during the same window.

## Timeline

- 14:05 UTC: A scheduled deploy of the Payments service completed, including an
  update to the service's database connection configuration
- 14:12 UTC: First 504 responses observed in Payments API monitoring, coinciding with
  the start of a marketing campaign that drove a 3x increase in checkout traffic
- 14:31 UTC: On-call engineer paged after error rate crossed the 5% alerting threshold
- 15:02 UTC: Root cause identified
- 15:20 UTC: Connection pool configuration reverted
- 15:47 UTC: Error rate returned to baseline

## Impact

Approximately 2,400 checkout attempts failed during the incident window. Affected
customers saw a generic "please try again" error at the payment confirmation step.

## Root Cause

The 14:05 UTC deploy included an unrelated configuration file cleanup that
inadvertently reset the Payments service's database connection pool size to its
framework default of 20 connections, down from the previously configured value of 100.
Under normal traffic this was not noticeable, since typical concurrent request volume
stayed well under 20. When the marketing-driven traffic surge began seven minutes
later, concurrent requests began queuing for a database connection, and queued
requests that waited longer than the gateway's timeout threshold were returned to
Checkout as 504 errors.

## Evidence

- Connection pool utilization metrics show the pool at 100% utilization continuously
  from 14:14 UTC onward, correlating tightly with the start of elevated error rates
- The deploy diff for the 14:05 UTC release shows the connection pool size setting was
  removed from the service's configuration file, causing it to fall back to the
  framework default
- Error logs from the affected window show error code PAY-1042 (connection pool
  exhausted) on the majority of failed requests
- No changes were made to the external payment processor integration in this release

## Resolution

The connection pool size was explicitly set back to 100 and deployed as a hotfix at
15:20 UTC. Error rates returned to baseline within the following 27 minutes as queued
requests drained.

## Follow-up Actions

- Add an explicit alert on connection pool utilization exceeding 80%, rather than
  relying solely on downstream error rate alerts
- Require configuration file diffs to be called out explicitly in deploy review for
  changes touching connection or resource limits
