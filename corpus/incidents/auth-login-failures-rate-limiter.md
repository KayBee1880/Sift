# INC-2024-0817: Elevated Authentication Login Failures

**Severity:** SEV3

## Summary

Between 11:20 and 13:05 UTC, a subset of users reported login failures with an
"invalid credentials" error despite entering correct passwords. Failures were not
uniform across all users.

## Timeline

- 10:55 UTC: A web application firewall rule update deployed, tightening per-IP
  request rate limits ahead of an anticipated bot traffic campaign
- 11:20 UTC: Support tickets begin arriving from users at two large corporate office
  networks reporting repeated login failures
- 11:48 UTC: On-call engineer paged after ticket volume crossed the alerting threshold
- 12:30 UTC: Root cause identified
- 12:50 UTC: Rate limit rule adjusted
- 13:05 UTC: Ticket volume returned to baseline

## Impact

An estimated 340 users across two corporate network ranges were unable to log in
during the affected window. Users on residential or mobile networks were not
affected.

## Root Cause

The 10:55 UTC WAF rule update applied a per-source-IP request rate limit that did not
account for network address translation. Users at large corporate offices share a
small number of public IP addresses across hundreds of employees. The new rule
treated the aggregate login traffic from each shared corporate IP as if it came from
a single abusive client, and began rejecting login attempts once the per-IP threshold
was crossed, regardless of how many distinct users were behind that IP.

## Evidence

- Rate limit counter metrics show the threshold being crossed specifically for two
  source IP addresses, both of which resolve to known corporate office network ranges
- Affected support tickets cluster almost entirely around users self-identifying as
  being in-office at those two locations; remote and mobile users reported no issues
- Authentication error logs show error code AUTH-4401 (rate limit exceeded) on
  rejected requests, not a credentials or session-related error
- Redis session store memory utilization remained within normal range throughout the
  incident, with only the ordinary gradual fluctuation seen on any given day
- A handful of unrelated support tickets during the window described slow page loads
  on an unrelated part of the site; investigation found no connection to this incident

## Resolution

The WAF rule was adjusted at 12:50 UTC to exempt known corporate IP ranges from the
per-IP threshold, with a broader per-IP rate limiting strategy left for follow-up
work.

## Follow-up Actions

- Design a rate limiting approach that accounts for shared corporate IP ranges before
  the next WAF rule change of this kind
- Add a known corporate IP range allowlist to future rate limit rule reviews
