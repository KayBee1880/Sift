# INC-2025-0304: Checkout Page Failure on Safari

**Severity:** SEV3

## Summary

Between 13:10 and 14:02 UTC, customers using Safari were unable to complete checkout.
The "Place Order" button did not respond to clicks. Other browsers were unaffected.

## Timeline

- 13:00 UTC: A Checkout frontend deploy shipped a bundling change consolidating
  several JavaScript modules
- 13:10 UTC: First reports of an unresponsive checkout button, all from Safari users
- 13:25 UTC: On-call engineer paged after Safari-specific error tracking crossed its
  alerting threshold
- 13:50 UTC: Root cause identified
- 14:02 UTC: Fix deployed, confirmed working

## Impact

Checkout completion for Safari users dropped to near zero during the incident
window, an estimated 9% of total checkout traffic. Chrome, Firefox, and Edge users
were unaffected throughout.

## Root Cause

The 13:00 UTC bundling change relied on a JavaScript syntax feature not yet supported
by the Safari version most commonly in use among customers. The unsupported syntax
caused the entire bundle to fail to parse in Safari, silently disabling all
interactivity on the checkout page, including the order submission handler, without
producing a visible error to the user.

## Evidence

- Frontend error tracking shows a parse error specific to Safari user agents,
  beginning at the exact deploy timestamp
- No corresponding errors appear for any other browser
- The specific syntax in question was confirmed unsupported in the affected Safari
  version range by checking browser compatibility documentation

## Resolution

The bundling configuration was updated to transpile the unsupported syntax for
broader browser compatibility, and redeployed at 14:02 UTC.

## Follow-up Actions

- Add automated cross-browser smoke testing to the Checkout frontend deploy pipeline,
  covering Safari specifically
- Review other recent bundling configuration changes for similar compatibility gaps
