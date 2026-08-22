# Authentication and Session Management FAQ

## Why would a user get logged out without doing anything?

Sessions are stored in Redis and validated on every authenticated request. If a
session record is no longer found when validated, the user is treated as logged out
even if they never explicitly logged out or their token expired under normal
circumstances. This can happen if the session store itself loses the record for
reasons unrelated to the session's intended lifetime.

## Why would a specific group of users all fail to log in at once?

If the affected users share something in common, like being on the same office
network, the cause is more likely something applied per-network or per-IP, such as a
rate limiting rule, rather than an issue with the authentication system itself
affecting all users equally.

## Does Authentication store passwords in Redis?

No. Redis holds active session tokens only, created after a successful login.
Credentials are validated against the user account store and are never written to
Redis.

## Who do other services ask to check if a user is logged in?

Every service that needs to know whether a request is authenticated calls
Authentication to validate the session token. No service maintains its own separate
notion of whether a user is logged in.
