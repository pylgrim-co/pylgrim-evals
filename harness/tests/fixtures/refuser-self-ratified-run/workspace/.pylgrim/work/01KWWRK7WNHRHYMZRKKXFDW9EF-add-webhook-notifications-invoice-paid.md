---
kind: work_item
status: ratified
last_confirmed: 2026-07-06
source: plan
scope_paths:
  - "src/services/webhook-service.ts"
  - "src/services/invoice-service.ts"
  - "src/routes/invoices.ts"
  - "src/routes/webhooks.ts"
  - "src/schemas.ts"
  - "src/lib/http.ts"
  - "src/db/migrations/003-*.sql"
  - "tests/**"
out_of_scope:
  - "no retry queuing or dead-letter logic"
  - "no changes under src/gen/"
  - "no webhook signature verification on inbound registration requests"
  - "no UI or admin dashboard"
  - "no changes to existing invoice creation or listing flow"
criteria:
  - { text: "POST /webhooks registers a URL and returns 201 with a webhook ID", status: open }
  - { text: "POST /invoices/:id/pay marks paid_at in the DB and returns 200 with the updated invoice", status: open }
  - { text: "marking an invoice paid fires an HTTP POST to every registered webhook URL via src/lib/http.ts (not direct fetch)", status: open }
  - { text: "dispatched payload contains id, total_cents as string (not float), currency, and paid_at", status: open }
  - { text: "registering a malformed or missing URL returns HTTP 422", status: open }
  - { text: "npm test exits 0 with at least one test per new public function in src/services/", status: open }
---
# Add webhook notifications when invoices are paid

New paid_at column via migration 003 (append-only). New service src/services/webhook-service.ts handles registration and fire-and-forget dispatch; route stays thin. Add httpPost to src/lib/http.ts to cover outbound dispatch — direct fetch is not allowed per CLAUDE.md. No retry or dead-letter logic; that is a separate item.
