# Data Flow: Checkout to Analytics

## Purpose

Describes how order and checkout event data moves from Checkout into Analytics
reporting.

## Event Publishing

Checkout publishes an event at each significant state change in the order
lifecycle: order created, fraud precheck result, charge submitted, charge result
received. Events are published asynchronously and do not block the customer-facing
checkout flow.

## Ingestion and Transformation

Analytics ingests published events into a raw event log, then runs a scheduled ETL
pipeline that transforms raw events into the aggregated tables backing reporting
dashboards. The pipeline runs on a fixed schedule rather than continuously.

## Expected Latency

Dashboard data reflects an expected lag of up to two hours behind real-time activity,
corresponding to the ETL pipeline's run frequency. This lag is normal and expected,
not itself an indication of a problem.

## Data Model

Aggregated tables include daily and hourly rollups of order volume, checkout
conversion rate (orders completed versus orders started), and fraud precheck
rejection rate. Raw event-level data is retained separately from the aggregated
tables; see the Data Retention and Access Policy for retention periods.

## Related Documentation

- Analytics Service
- ETL Pipeline Failure Recovery
