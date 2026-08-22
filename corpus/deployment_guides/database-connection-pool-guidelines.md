# Database Migration and Connection Pool Configuration Guidelines

## Purpose

General guidance for engineers configuring or modifying database connection pool
settings for any internal service.

## Recommended Configuration

Connection pool size should be set explicitly in each service's configuration rather
than left at a client library's default value. Defaults are typically tuned for
low-traffic general use and are frequently too small for a production service under
real load.

## Sizing Guidelines

A reasonable starting point is to size the pool to comfortably exceed the service's
measured peak concurrent database operations, with headroom for traffic growth and
short-term spikes such as marketing campaigns or seasonal events. Pool size should be
revisited whenever a service's traffic profile changes materially.

## Change Management

Any change to a service's connection pool configuration, including changes made as a
side effect of unrelated configuration file edits, should be called out explicitly in
the deploy's review description. Configuration file refactors and cleanups are a
common source of unintended changes to resource limits, since such changes do not
always show up prominently in a diff review focused on the primary purpose of the
change.

## Monitoring

Every service with a configured connection pool should have alerting on pool
utilization, not only on downstream symptoms such as elevated error rates or latency.
Utilization-based alerting surfaces resource exhaustion before it produces
customer-facing impact.
