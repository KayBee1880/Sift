# ETL Pipeline Failure Recovery

## Purpose

Guidance for diagnosing and recovering from a failed or stalled Analytics ETL
pipeline run.

## Symptoms

- Dashboard figures have not updated within the expected lag window
- Pipeline monitoring shows a failed run, or no successful run within the expected
  schedule interval

## Diagnostic Steps

1. Check the timestamp of the last successful pipeline run against the expected
   schedule
2. Review pipeline logs for the most recent run for an explicit error
3. Check whether consecutive runs have failed at the same checkpoint, which
   indicates the failure is not transient and will not resolve itself on the next
   scheduled run
4. Check for any unrelated infrastructure maintenance or incidents around the time
   of the first failure

## Resolution Steps

1. If a single run failed transiently and the next scheduled run succeeded, no
   action is needed
2. If runs are failing repeatedly at the same checkpoint, the checkpoint state
   likely needs to be manually cleared before the pipeline can proceed. Do not simply
   re-trigger the same run repeatedly without addressing the checkpoint
3. After clearing a bad checkpoint, manually trigger a pipeline run and confirm it
   processes successfully before assuming the issue is resolved

## Escalation

Escalate to the Data Platform team lead if the checkpoint state cannot be identified
or cleared through standard tooling.

## Related Documentation

- Analytics Service
- Data Flow: Checkout to Analytics
