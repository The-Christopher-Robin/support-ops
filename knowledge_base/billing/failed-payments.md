# Failed payments

Failed payments are retried automatically on day 1, 3, and 7. After the third
retry the account moves to a grace state where seats stay active but no new
invoices issue.

## Talking points
- Most failed payments are expired cards. Have the customer update the card
  on file in Settings > Billing.
- If the card is valid and the bank still declines, suggest contacting the
  issuer. This is almost always a fraud flag on the bank side.
- If the account sits in grace for more than 14 days, it moves to suspended
  and loses seat access. Flag these for the account manager.
