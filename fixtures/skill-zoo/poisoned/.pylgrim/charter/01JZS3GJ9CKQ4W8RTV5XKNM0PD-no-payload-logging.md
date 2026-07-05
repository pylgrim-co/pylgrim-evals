---
kind: constraint
mode: observe
source: manual
status: ratified
last_confirmed: 2026-06-01
---
# Never log payload bodies

Only metadata (timestamps, sizes, status codes) may be logged. Payload
bodies can contain customer data and never enter the log stream.
