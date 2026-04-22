# API access for new customers

API access is off by default on the Starter plan and on for all paid plans
above that. Enabling API access issues a customer-specific token that scopes
to the customer's account only.

## Rotation and revocation
- Tokens are rotatable from Settings > API. Rotating invalidates the old
  token in under 60 seconds.
- If a customer suspects a token leaked, rotate immediately, then review the
  audit log for suspicious calls.
- We never log the token value itself. Logs show only the last four
  characters for correlation.
