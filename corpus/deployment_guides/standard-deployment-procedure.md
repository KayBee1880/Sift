# Standard Service Deployment Procedure

## Purpose

Defines the standard process for deploying changes to any internal service.

## Pre-Deploy Requirements

- Changes must be reviewed and approved by at least one other engineer before merge
- The review description must summarize the intended change and call out any
  modification to configuration, resource limits, or external integrations, even if
  such a modification is a side effect of a broader change rather than its primary
  purpose
- Automated tests must pass before merge

## Deploy Process

1. Merge to the main branch triggers a build and automated test run
2. On success, the change is deployed to a staging environment for a smoke test
3. On successful smoke test, the change is deployed to production
4. The deploying engineer monitors key service dashboards for at least 15 minutes
   following a production deploy

## Rollback

Any service deploy can be rolled back to the previous release through the deployment
tooling. Rollback should be the first response to a suspected deploy-related
incident, root cause investigation can continue after service is restored.

## Scope

This procedure applies to all internal services. Some services maintain
service-specific deployment guides for procedures beyond this general process, such
as the Checkout Deployment Rollback Procedure.
