# Payment Decline Troubleshooting

## Purpose

Guidance for investigating transactions declined by the card issuer after reaching
Payments.

## Symptoms

- Customer reports the payment was declined or unsuccessful
- The order record shows a Payments transaction was created and a response was
  received from the external payment processor, the request did reach Payments and
  was forwarded to the card network

## How Issuer Declines Work

Once a charge request reaches Payments, it is forwarded to the payment processor,
which relays it to the customer's card-issuing bank. The issuer returns a response
code indicating approval or the specific reason for decline, such as insufficient
funds, an expired card, or a suspected-fraud hold placed by the issuer itself. Payments
does not have visibility into why an issuer declined a transaction beyond the response
code provided.

## Diagnostic Steps

1. Look up the transaction in Payments gateway logs and confirm a response was
   received from the processor
2. Note the issuer response code and its associated reason
3. Check whether the customer has had other transactions decline for the same reason
   recently, which may indicate the underlying issue is with their card rather than
   with our systems

## Resolution Steps

Issuer declines are not resolvable on our end. The standard guidance is for the
customer to contact their card issuer directly or attempt payment with a different
card. Do not retry the same card automatically, repeated retries against a declining
card can trigger additional fraud holds from the issuer.

## Related Documentation

- Payments Service (overview, error code PAY-3011)
- Payments and Checkout FAQ
