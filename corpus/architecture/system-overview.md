# System Architecture Overview

## Purpose

This document describes how the five core services, Payments, Checkout,
Authentication, Notifications, and Analytics, fit together. It is the starting point
for understanding cross-service behavior; each service's own documentation covers its
internals in more depth.

## Service Dependencies

- **Checkout depends on Payments.** Checkout orchestrates the purchase flow and, once
  an order is confirmed and passes its own fraud pre-check, submits a charge request to
  Payments. Payments is the only service that communicates with the external payment
  processor.
- **Checkout depends on Notifications.** After a successful charge, Checkout requests
  an order confirmation email.
- **All services depend on Authentication.** Every request to Payments, Checkout,
  Notifications, or Analytics that requires a user identity is validated against
  Authentication's session store first.
- **Analytics depends on all other services.** Payments, Checkout, Authentication, and
  Notifications each publish events that Analytics ingests for reporting. This
  dependency is one-directional: no service depends on Analytics to function.

## Request Flow: A Typical Purchase

1. Customer authenticates (Authentication issues a session)
2. Customer builds a cart and submits an order (Checkout)
3. Checkout runs a fraud pre-check. If rejected, the flow stops here and Payments is
   never contacted
4. Checkout submits a charge request to Payments
5. Payments contacts the external payment processor and returns an accept, decline, or
   error result to Checkout
6. On success, Checkout requests a confirmation email from Notifications
7. Each service involved publishes an event to Analytics

## Data Ownership

Each service owns its own data store. There is no shared database between services;
cross-service data access happens through service APIs or, for reporting purposes,
through the Analytics event stream.

## Related Documentation

- Payments Service Architecture
- Data Flow: Checkout to Analytics
