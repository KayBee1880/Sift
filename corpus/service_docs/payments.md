# Payments Service

## Overview

The Payments service handles authorization, capture, and settlement of customer
payment transactions. It is the system of record for transaction state and is the
only service permitted to communicate directly with our external payment processor.
Every purchase that reaches the point of an actual charge attempt passes through this
service.

## Ownership

Owned by the Payments team. On-call rotation covers business hours plus a 24/7
pager for SEV1/SEV2 incidents, see the Incident Severity Classification Policy for
definitions.

## Dependencies

- PostgreSQL: primary data store for transaction and charge records
- External payment processor: reached over an outbound HTTPS connection secured with
  a client certificate; Payments is the only internal service with credentials to call it
- Checkout service: the primary internal caller of the Payments API. Checkout submits
  a charge request once a customer confirms an order

## API Overview

The service exposes an internal REST API for charge creation, charge status lookup,
and refund initiation. Charge creation is synchronous from the caller's perspective:
Checkout waits for a definitive accept, decline, or error response before completing
the customer-facing checkout flow.

## Common Error Codes

| Code | Meaning |
|---|---|
| PAY-1042 | Connection pool exhausted |
| PAY-2087 | Upstream TLS handshake failure with the payment processor |
| PAY-3011 | Transaction declined by the card issuer |
| PAY-5090 | Internal server error during charge calculation |

Troubleshooting steps for each code live in their respective runbooks or incident
postmortems, not here.

## Related Documentation

- Payments Service Architecture (internal design, connection pool configuration)
- Gateway Timeout Troubleshooting runbook
- Payment Decline Troubleshooting runbook
