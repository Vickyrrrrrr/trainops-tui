# Future Web Client

The web client is intentionally deferred for v1.

When it is built, it should consume the same backend contracts as the Textual
client:

- Versioned REST routes under `/api/v1`
- Server-sent events from `/api/v1/streams/runs/{run_id}`
- Signed approval actions through `/api/v1/approvals/{run_id}`
- Dataset review, plan approval, evaluation, publication, and audit records from
  the same resources used by the TUI

No separate workflow semantics should be introduced in the web client.

