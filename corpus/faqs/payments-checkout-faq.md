# Payments and Checkout FAQ

Common questions from engineers new to these services.

## A customer says their payment was declined. Where do I even start?

First check whether the order ever reached Payments at all. Some orders get stopped
by Checkout's own fraud screening before a charge is ever attempted, in which case
there's no card issuer involved and nothing to investigate on the Payments side. If
the order did reach Payments, the decline came from the customer's card issuer, and
our systems don't have insight into the issuer's specific decision beyond the
response code they returned.

## What's the difference between a "decline" and a "timeout"?

A decline means a definite answer was returned, either the fraud precheck rejected
the order, or the card issuer rejected the charge. A timeout means no answer was ever
received in time, something in the request path (commonly the database or the
outbound connection to the processor) failed to respond before the gateway gave up.
The customer experience can look similar, but the underlying causes and fixes are
completely different.

## Does Checkout ever talk to the card network directly?

No. Only Payments communicates with the external payment processor. Checkout's role
ends at deciding whether to submit a charge request to Payments at all.

## Can I just retry a declined payment automatically?

Not for issuer declines, repeated automatic retries against the same card can trigger
additional fraud holds from the issuer. Fraud precheck rejections can be manually
reviewed and resubmitted if judged a false positive.
