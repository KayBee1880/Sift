# Data Retention and Access Policy

## Purpose

Defines how long different categories of data are retained and who is permitted to
access them.

## Retention Periods

- Transaction and order records: retained for 7 years, in line with financial
  record-keeping requirements
- Raw event logs (feeding Analytics): retained for 90 days, after which only the
  aggregated reporting tables persist
- Authentication session records: retained for the lifetime of the session plus 30
  days for security audit purposes, then deleted
- Support ticket records: retained for 3 years

## Access Control

Access to raw transaction and order data is restricted to the Payments and Checkout
teams and a limited set of support engineers with a documented business need.
Aggregated Analytics data is broadly accessible to internal staff for reporting
purposes, since it does not contain individually identifiable transaction detail.

## Data Minimization

Services should avoid storing data beyond what is operationally necessary. New data
fields added to any service's schema should have an explicit retention period
assigned at the time they are introduced, not left to default to indefinite
retention.

## Review

This policy is reviewed annually by the Platform team in coordination with Legal.
