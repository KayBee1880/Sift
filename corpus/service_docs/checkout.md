# Checkout Service

## Overview

The Checkout service orchestrates the customer-facing purchase flow: cart review,
address and shipping selection, a fraud pre-screening step, and finally submitting the
transaction to Payments for charging. It owns the order record from creation through
confirmation.

## Ownership

Owned by the Checkout team.

## Dependencies

- Payments service: Checkout calls Payments to charge the customer once an order is
  confirmed and has passed fraud pre-screening. Checkout does not process card details
  itself
- Notifications service: Checkout requests an order confirmation email be sent once a
  charge succeeds
- Authentication service: Checkout requires an authenticated session to begin an order
- PostgreSQL: order and cart state

## API Overview

Checkout exposes endpoints for cart management, order creation, and order confirmation
retrieval. Order submission runs an internal fraud pre-check before any request is sent
to Payments. Orders that fail the pre-check are rejected without ever reaching the
Payments API.

## Common Error Codes

| Code | Meaning |
|---|---|
| CHK-4400 | Order rejected by fraud pre-check |

A charge that fails after reaching Payments surfaces a Payments-originated error code
instead, not a Checkout code, see the Payments service documentation.

## Related Documentation

- System Architecture Overview
- Checkout Fraud Precheck Rejection runbook
- Checkout Deployment Rollback Procedure
