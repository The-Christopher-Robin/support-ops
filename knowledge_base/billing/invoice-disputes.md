# Invoice disputes

Customers sometimes flag a charge they do not recognize. Before issuing a
refund, verify the invoice in Stripe and cross-check the customer's plan tier.

## Steps
1. Ask for the invoice number or last four of the card used.
2. Pull the invoice detail view in Stripe.
3. Compare the line items to the customer's plan tier on our side.
4. If the mismatch is legitimately our error, refund the delta and note the
   ticket ID in the invoice metadata.
5. If the charge is correct, walk the customer through the line items and
   offer a walkthrough of their plan before escalating.
