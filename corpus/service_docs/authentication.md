# Authentication Service

## Overview

The Authentication service issues and validates user sessions for every other
internal service. It handles login, session creation, session validation, and logout.
No other service maintains its own notion of user identity.

## Ownership

Owned by the Platform team.

## Dependencies

- PostgreSQL: user account records
- Redis: active session storage. Session tokens are validated against Redis on every
  authenticated request, not just at login
- Called by every other service (Checkout, Payments, Notifications, Analytics) to
  validate incoming session tokens

## API Overview

Login accepts credentials and, on success, creates a session record in Redis and
returns a session token to the client. Session validation is a fast Redis lookup by
token. Logout deletes the session record.

## Common Error Codes

| Code | Meaning |
|---|---|
| AUTH-4401 | Rate limit exceeded |
| AUTH-5501 | Session not found |

## Related Documentation

- Login Failure Triage Guide
- Authentication and Session Management FAQ
