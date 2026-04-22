# Webhook failures from integration partners

When a partner webhook fails delivery, we retry with exponential backoff for
up to 24 hours. After that the event is dead-lettered and surfaces on the
admin's Integrations dashboard.

## What to do with a dead-lettered event
- Check the partner's status page first. Partner-side outages are the most
  common cause and will resolve themselves once the partner recovers.
- If the partner is healthy, replay the event from the admin dashboard.
  Replays re-enter the normal retry queue and do not re-trigger downstream
  side effects that already succeeded.
- If the replay also fails, open a ticket with the partner including the
  event ID, the failing payload hash, and the first and last retry times.
