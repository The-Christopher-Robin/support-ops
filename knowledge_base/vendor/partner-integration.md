# Vendor / partner integrations

We maintain integrations with a handful of partner platforms for payroll,
accounting, and HRIS data sync. When an integration breaks, the root cause
is almost always one of three things.

## Diagnostic checklist
1. Expired API token: check Settings > Integrations > Status. Red tokens
   need the customer to re-authorize the connection.
2. Rotated webhook URL: if the partner rotated their webhook endpoints, our
   webhooks will 404. Refresh the partner's webhook manifest.
3. Schema drift: partners sometimes change fields without version bumps.
   Check the last successful sync's payload against the latest one.
