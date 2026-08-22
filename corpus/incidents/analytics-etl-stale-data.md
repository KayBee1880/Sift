# INC-2025-0417: Analytics Dashboards Showing Stale Data

**Severity:** SEV3

## Summary

Analytics dashboards displayed data that was approximately 14 hours out of date,
well beyond the normal expected lag, for a period spanning roughly one business day
before being noticed and resolved.

## Timeline

- Day 1, 02:00 UTC: The scheduled ETL pipeline run failed partway through, an
  unrelated database maintenance window caused a connection interruption mid-run
- Day 1, 02:00 UTC onward: Subsequent scheduled runs also failed, each one attempting
  to process from the same failed checkpoint
- Day 2, 09:40 UTC: A Data Platform team member noticed dashboard figures had not
  changed since the previous day and opened an investigation
- Day 2, 10:15 UTC: Root cause identified
- Day 2, 10:50 UTC: Pipeline manually restarted from a corrected checkpoint
- Day 2, 12:30 UTC: Dashboards caught up to current data

## Impact

No customer-facing impact. Internal stakeholders relying on Analytics dashboards for
same-day reporting had stale figures for roughly a full business day before the issue
was noticed.

## Root Cause

A database maintenance window unrelated to Analytics caused a transient connection
interruption during the scheduled ETL run. The pipeline's error handling did not
distinguish between a transient failure and a data integrity problem, and defaulted
to retrying from its last saved checkpoint on the next scheduled run. Because that
checkpoint was itself mid-write when the connection dropped, every subsequent run
failed the same way, and no alert existed for repeated pipeline failures, only for a
single run's success or failure status individually.

## Evidence

- Pipeline run logs show the same checkpoint failure recurring on every scheduled run
  starting Day 1, 02:00 UTC
- The database maintenance window's timing matches the first failure exactly
- No alert fired because each individual run reported a normal failure status; there
  was no monitoring for the pattern of repeated consecutive failures

## Resolution

The corrupted checkpoint was manually cleared and the pipeline restarted from the
last known-good state at 10:50 UTC. The pipeline caught up to current data over the
following period as it processed the backlog.

## Follow-up Actions

- Add alerting for repeated consecutive pipeline failures, not just individual run
  status
- Make checkpoint writes atomic so a mid-write interruption cannot leave a corrupted
  checkpoint behind
