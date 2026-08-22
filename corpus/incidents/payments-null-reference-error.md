# INC-2025-0611: Payments API Elevated 500 Error Rate

**Severity:** SEV3

## Summary

Between 20:14 and 21:02 UTC, approximately 4% of charge requests failed with a 500
Internal Server Error rather than completing or returning a normal decline response.

## Timeline

- 19:50 UTC: A deploy shipped a change to support a new promotional discount code
  format
- 20:14 UTC: 500 error rate on charge requests begins climbing
- 20:22 UTC: On-call engineer paged
- 20:45 UTC: Root cause identified
- 20:58 UTC: Hotfix deployed
- 21:02 UTC: Error rate returned to baseline

## Impact

An estimated 210 checkout attempts failed with a 500 error. Affected orders all
involved a promotional discount code applied to a cart containing exactly one line
item.

## Root Cause

The 19:50 UTC deploy introduced a code path to calculate discount amounts for the new
promotional code format. The charge calculation function assumed a cart's line item
list and its associated pricing breakdown were always populated together, but for
carts with a single line item, the pricing breakdown object was left unset in one
specific case, when the discount reduced the item's price to exactly zero. Attempting
to read a field from the unset pricing breakdown object raised a null reference
error, which propagated up as a 500 response instead of being handled.

## Evidence

- Error logs show error code PAY-5090 (internal server error during charge
  calculation) with a stack trace pointing to the new discount calculation function
  introduced in the 19:50 UTC deploy
- All affected requests involve a cart with exactly one line item and a discount code
  that reduces the item price to zero
- The error began immediately following the 19:50 UTC deploy with no other
  correlated change
- Database connection pool and outbound processor connectivity metrics remained
  normal throughout, ruling out the causes covered in the Gateway Timeout
  Troubleshooting runbook

## Resolution

A hotfix was deployed at 20:58 UTC to explicitly handle the zero-price case in the
discount calculation function rather than assuming the pricing breakdown object was
always populated.

## Follow-up Actions

- Add a test case covering single-line-item carts with a discount reducing price to
  zero
- Add input validation at the start of the charge calculation function to fail with a
  clear error rather than a null reference exception when required fields are
  unexpectedly unset
