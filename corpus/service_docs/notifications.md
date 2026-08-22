# Notifications Service

## Overview

The Notifications service sends transactional messages to customers on behalf of
other internal services. It currently supports two delivery channels: email and SMS.

## Ownership

Owned by the Platform team.

## Dependencies

- Email delivery: a third-party SMTP provider
- SMS delivery: a third-party SMS gateway provider
- PostgreSQL: delivery status and retry tracking
- Called by Checkout (order confirmation emails) and Authentication (SMS-based login
  verification codes)

## API Overview

Callers submit a notification request specifying a template, a channel (email or
SMS), and recipient details. Delivery is asynchronous: the service queues the request
and returns immediately, with delivery status queryable afterward.

## Common Error Codes

| Code | Meaning |
|---|---|
| NOTIF-3009 | SMS provider quota exceeded |

## Related Documentation

- Notification Delivery Failure Troubleshooting
