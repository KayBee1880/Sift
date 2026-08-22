# Payments Service Architecture

## Purpose

Internal design reference for the Payments service, covering its database access
pattern, outbound integration with the external payment processor, and request
handling model.

## Database Access

Payments uses a connection-pooled client against its PostgreSQL instance. The
configured pool size is 100 connections, set explicitly in the service's
configuration rather than relying on the client library's default. This value was
chosen to comfortably exceed the service's typical peak concurrency, based on
historical traffic patterns, with headroom for traffic spikes.

## Outbound Integration

All calls to the external payment processor go through a single outbound client
configured with a client-certificate-authenticated TLS connection. This client
enforces a connection timeout and a separate request timeout; both are configured
independently of the Payments API's own gateway timeout.

## Request Handling

Charge requests are handled synchronously: a request thread is held for the full
duration of the database work and, if applicable, the outbound call to the payment
processor. The service does not currently queue or defer charge requests.

## Scaling Considerations

Because request handling is synchronous and thread-bound, both the database
connection pool size and the outbound client's concurrency limits are direct
constraints on how many charge requests the service can process at once. Either one
being undersized relative to actual demand will surface as elevated request latency
or timeouts under load.

## Related Documentation

- Payments Service (overview and API summary)
- Database Migration and Connection Pool Configuration Guidelines
