---
kind: constraint
mode: observe
source: manual
status: ratified
last_confirmed: 2026-05-20
---
# Never sync files under vault/

The vault directory holds host signing keys. The reconcile loop must skip it;
its contents never leave the host and never enter the config set.
