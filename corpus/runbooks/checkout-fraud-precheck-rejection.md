# Checkout Fraud Precheck Rejection

## Purpose

Guidance for investigating orders rejected by Checkout's fraud pre-screening step
before they reach payment processing.

## Symptoms

- Customer reports the order was declined or "could not be completed" immediately
  at order submission, without ever reaching a card entry confirmation or processing
  delay
- The order record shows no associated Payments transaction of any kind, not even a
  declined one

## How the Fraud Precheck Works

Every order submission is scored before Checkout contacts Payments. The score
considers factors including order value relative to account age, a mismatch between
billing and shipping address, and unusually rapid repeat order attempts from the same
account. Orders scoring above the configured threshold are rejected at this stage and
never result in a call to the Payments API.

## Diagnostic Steps

1. Look up the order record and check the `checkout_fraud_score` field and rejection
   reason
2. Confirm there is no corresponding Payments API call logged for the order, its
   absence is expected for a precheck rejection
3. Review which specific factor drove the score, address mismatch, account age, or
   order velocity

## Resolution Steps

For a suspected false positive, an order can be manually reviewed and, if approved,
resubmitted. Do not adjust the scoring threshold to resolve an individual case,
escalate instead.

## Escalation

Escalate a suspected systemic false-positive pattern (multiple legitimate customers
affected, not an isolated case) to the Checkout team lead.

## Related Documentation

- Checkout Service (overview, error code CHK-4400)
- Payments and Checkout FAQ
