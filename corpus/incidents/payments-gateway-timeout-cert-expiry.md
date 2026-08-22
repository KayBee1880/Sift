# INC-2025-0203: Payments API Gateway Timeout

**Severity:** SEV2

## Summary

Between 09:03 and 10:15 UTC, the Payments API returned 504 Gateway Timeout responses
for the majority of charge requests. Checkout reported widespread order failures
during the same window.

## Timeline

- 09:03 UTC: 504 error rate begins climbing sharply, reaching 60% of charge requests
  within four minutes
- 09:08 UTC: On-call engineer paged
- 09:35 UTC: Database and application metrics for the Payments service checked and
  found normal; investigation shifted to the outbound connection to the external
  payment processor
- 09:52 UTC: Root cause identified
- 10:05 UTC: Certificate rotated
- 10:15 UTC: Error rate returned to baseline

## Impact

Approximately 6,100 checkout attempts failed during the incident window, the highest
single-incident order failure count recorded for Payments to date.

## Root Cause

The TLS client certificate used to authenticate the Payments service's outbound
connection to the external payment processor expired at 09:00 UTC. The processor's
endpoint did not reject the connection outright; instead, each connection attempt
hung for the full duration of the TLS handshake timeout before failing. Because these
hung connections held request threads open far longer than a normal request, the
gateway timeout was reached before Payments ever received a response from the
processor.

## Evidence

- The expired certificate's validity end date matches the incident start time exactly
- Application logs show elevated request duration for outbound calls to the payment
  processor beginning at 09:00 UTC, with durations clustering around the TLS handshake
  timeout value rather than typical processor response times
- Error logs show error code PAY-2087 (upstream TLS handshake failure) on affected
  requests
- No deploy or configuration change occurred in the 24 hours preceding the incident
- Database connection pool utilization remained within normal range throughout the
  incident

## Resolution

A new certificate was issued and deployed at 10:05 UTC. Error rates began recovering
immediately as new connection attempts succeeded; the residual elevated error rate
until 10:15 UTC reflected in-flight requests that had already begun hanging before
the fix was deployed.

## Follow-up Actions

- Add automated alerting for certificates nearing expiration, at 30 and 7 days prior
- Investigate whether the outbound connection timeout to the payment processor can be
  shortened so that certificate or network failures fail fast rather than hanging for
  the full handshake duration
