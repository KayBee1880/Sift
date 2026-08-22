# Incident Severity Classification Policy

## Purpose

Defines the severity levels used to classify incidents across all services, so
impact and response expectations are consistent regardless of which team is
involved.

## Severity Levels

**SEV1: Critical.** Complete or near-complete outage of a core user-facing flow
(checkout, login) affecting all or nearly all users. Requires immediate all-hands
response and executive notification.

**SEV2: Major.** Significant degradation or partial outage affecting a large
proportion of users or a core flow, but not a complete outage. Requires immediate
on-call response.

**SEV3: Moderate.** Degradation affecting a limited subset of users or a
non-critical flow. Requires on-call response within normal paging expectations but
not necessarily immediate escalation.

**SEV4: Minor.** Low-impact issue with minimal or no direct user impact. Can
typically be handled during normal business hours.

## Classification Responsibility

The on-call engineer assigns initial severity at the time of paging, based on
observed impact. Severity may be adjusted as more information becomes available
during the incident and should be finalized in the postmortem.

## Postmortem Requirements

SEV1 and SEV2 incidents require a written postmortem within five business days.
SEV3 and SEV4 postmortems are recommended but not mandatory.
