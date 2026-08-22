# Login Failure Triage Guide

## Purpose

Guidance for on-call engineers investigating a reported increase in login failures
or unexpected logouts.

## Symptoms

- Support tickets or monitoring showing elevated login failure or session validation
  error rates
- User reports vary: some describe being unable to log in at all, others describe
  being logged out unexpectedly after a successful login

## Diagnostic Steps

1. Determine whether affected reports are concentrated among specific networks or
   IP ranges, or spread evenly across all users. Concentration by network origin
   points toward a rate limiting or WAF-related cause; even distribution points
   toward an infrastructure issue affecting the session store itself
2. Check Redis session store memory utilization and eviction metrics
3. Check for recent WAF or rate limit rule changes and correlate their deploy time
   against the onset of reports
4. Review Authentication error logs for the specific error code associated with
   failed requests, different underlying causes surface different codes, see the
   Authentication service documentation's error code table
5. Check whether affected users report having been logged in successfully shortly
   before the failure, which suggests an existing session being invalidated rather
   than a login-time credentials problem

## Common Causes

Login failure incidents on this service have stemmed from both overly aggressive
rate limiting misapplied to shared IP addresses, and from session store resource
pressure causing active sessions to be evicted. The two present differently in terms
of which users are affected and should be distinguishable using the diagnostic steps
above.

## Resolution Steps

Resolution depends on the diagnosed cause. Rate limiting issues are typically
resolved by adjusting the offending rule; session store issues are typically
resolved by addressing the resource constraint directly.

## Escalation

If the affected user population's pattern does not clearly indicate one cause after
initial triage, escalate to the Platform team lead.
