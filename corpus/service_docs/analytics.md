# Analytics Service

## Overview

The Analytics service ingests events from every other internal service and produces
aggregated reporting data: transaction volumes, checkout conversion rates, login
activity, and notification delivery rates. It is read-only from the perspective of the
services it observes.

## Ownership

Owned by the Data Platform team.

## Dependencies

- Event stream from Payments, Checkout, Authentication, and Notifications, each
  service publishes events on state changes relevant to reporting
- An ETL pipeline that runs on a scheduled basis to transform raw events into
  aggregated tables
- PostgreSQL: both the raw event log and the aggregated reporting tables

## API Overview

Analytics exposes read-only endpoints for dashboard queries against the aggregated
tables. It does not expose any endpoint for other services to call synchronously,
all input arrives via the event stream.

## Related Documentation

- ETL Pipeline Failure Recovery
- Data Flow: Checkout to Analytics
