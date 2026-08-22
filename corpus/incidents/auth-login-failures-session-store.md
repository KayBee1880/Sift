# INC-2025-0130: Elevated Authentication Login Failures

**Severity:** SEV2

## Summary

Between 16:40 and 17:55 UTC, users broadly across all networks and regions
experienced unexpected logouts and login failures. Unlike a typical credentials
issue, many affected users reported having been logged in successfully just minutes
earlier.

## Timeline

- 16:35 UTC: Redis session store memory utilization crosses 90% for the first time,
  not yet alerting
- 16:40 UTC: Users begin reporting being unexpectedly logged out mid-session
- 16:58 UTC: On-call engineer paged after error rate on session validation requests
  crossed the alerting threshold
- 17:20 UTC: Root cause identified
- 17:35 UTC: Session store memory limit increased
- 17:55 UTC: Error rate returned to baseline

## Impact

Session validation failures affected an estimated 2,900 active sessions across all
user segments and networks, with no concentration by geography or network origin.

## Root Cause

The Redis instance backing session storage reached its configured memory limit.
Redis's eviction policy for this instance is least-recently-used, meaning that once
the limit was reached, it began evicting session records to make room for new ones,
including sessions belonging to users who were actively using the product. Evicted
sessions were treated as invalid on their next validation check, producing a login
failure or unexpected logout even though the user's original login had succeeded.

## Evidence

- Redis memory utilization metrics show a gradual climb to 100% over the preceding
  several hours, driven by organic session volume growth rather than any single
  event, with eviction beginning once the limit was reached
- Redis eviction event logs show a sustained eviction rate beginning at 16:40 UTC,
  correlating exactly with the start of user reports
- Authentication error logs show error code AUTH-5501 (session not found) on affected
  requests, not a rate limit or credentials error
- Affected user reports are distributed evenly across geographic regions and network
  types, with no clustering by IP range or network origin
- No WAF or rate limit configuration changes occurred in the preceding 48 hours, and
  rate limit counters remained within normal range throughout the incident
- Application server CPU utilization showed a brief, unrelated uptick around 16:50
  UTC, consistent with normal load variance and not linked to the session store issue

## Resolution

The Redis instance's memory limit was increased at 17:35 UTC. Eviction stopped
immediately, though users who had already been logged out needed to log in again
manually; sessions could not be recovered after eviction.

## Follow-up Actions

- Add alerting on Redis memory utilization at 75% and 90%, ahead of the eviction
  threshold
- Evaluate whether session records should have a maximum time-to-live independent of
  memory pressure, so that eviction under load happens predictably rather than via
  LRU across active and inactive sessions alike
