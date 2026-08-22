# Notification Delivery Failure Troubleshooting

## Purpose

Guidance for investigating delayed or failed notification delivery over email or
SMS.

## Symptoms

- Delivery status queries show messages stuck in a pending or retrying state
- Customer or internal reports of missing order confirmation emails or SMS
  verification codes

## Diagnostic Steps

1. Check delivery queue depth and retry count for the affected channel
2. Check the relevant provider's public status page for an acknowledged outage,
   email and SMS use separate third-party providers, so an issue with one does not
   imply an issue with the other
3. Check for a quota-related error specifically, distinct from a general delivery
   failure

## Common Causes

- Third-party provider service disruption, delivery is queued and retried
  automatically, no message loss expected, but delivery latency increases for the
  duration
- Quota exceeded (error code NOTIF-3009): the SMS provider account has a monthly
  message quota. Once exceeded, new SMS sends fail immediately rather than being
  queued for retry, since retrying will not succeed until the quota resets. Confirm
  quota status directly with the provider account dashboard. If quota exhaustion is
  confirmed, an emergency quota increase can be requested from the provider, contact
  the Notifications on-call lead for provider account access

## Resolution Steps

For a provider disruption, no action is typically needed beyond monitoring queue
drain once the provider recovers. For quota exhaustion, either wait for quota reset
or escalate for an emergency increase, depending on urgency.

## Escalation

Escalate to the Platform team lead if delivery has not recovered within 30 minutes
of a provider status page reporting resolution, which may indicate a separate issue
on our own side.
