# Gateway Timeout Troubleshooting

## Purpose

Guidance for on-call engineers investigating 504 Gateway Timeout errors from the
Payments API.

## Symptoms

- Elevated 504 response rate on Payments API endpoints, visible in the Payments
  dashboard
- Checkout reporting failed orders with a generic payment error
- Customer-facing impact is usually reported as "checkout isn't working" or "payment
  failed" rather than anything specific to a timeout

## Diagnostic Steps

1. Check the Payments dashboard for database connection pool utilization. Sustained
   utilization near 100% points toward a resource exhaustion cause
2. Check outbound request duration to the external payment processor. Durations
   clustering near the configured handshake or connection timeout, rather than typical
   processor response times, point toward a connectivity or certificate issue on the
   outbound leg
3. Check whether a deploy occurred in the window immediately before the error rate
   increased. Correlate the deploy diff against the symptom onset time
4. Check whether the error rate increase correlates with a traffic increase (marketing
   campaigns, seasonal spikes) rather than a deploy
5. Review recent error codes in the Payments error logs; different underlying causes
   surface with different codes, see the Payments service documentation's error code
   table

## Common Causes

Historically, gateway timeouts on this service have stemmed from either database
connection pool exhaustion or issues with the outbound connection to the external
payment processor (including certificate problems). Both present with similar
customer-facing symptoms; the diagnostic steps above are intended to distinguish them
before applying a fix, since the two failure modes require different remediations.

## Resolution Steps

Resolution depends on the diagnosed cause. Do not apply a fix without first
completing the diagnostic steps above, a fix appropriate to one cause will not resolve
the other and may extend the incident unnecessarily.

## Escalation

If the cause cannot be determined within 20 minutes of initial triage, escalate to
the Payments team lead and open a SEV2 incident per the Incident Severity
Classification Policy.
