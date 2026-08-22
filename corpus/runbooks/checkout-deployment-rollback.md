# Checkout Deployment Rollback Procedure

## Purpose

Service-specific rollback steps for the Checkout service, supplementing the Standard
Service Deployment Procedure.

## When to Roll Back

Roll back a Checkout deploy if error rates on order submission or fraud precheck
endpoints increase noticeably following a release, and the change cannot be quickly
identified as unrelated.

## Rollback Steps

1. Identify the previous stable release version from the deployment tooling
2. Trigger a rollback deploy to that version
3. Confirm order submission error rates return to baseline within 10 minutes of
   rollback completing
4. If error rates do not recover, the issue is likely not deploy-related, continue
   investigation rather than attempting a further rollback

## Frontend and Backend Coordination

Checkout ships frontend and backend changes on independent release cadences. A
rollback of one does not automatically roll back the other, confirm which side
introduced the regression before deciding what to roll back.

## Related Documentation

- Standard Service Deployment Procedure
- Checkout Service
