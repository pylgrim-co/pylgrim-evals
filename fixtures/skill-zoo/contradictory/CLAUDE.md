# relay: webhook fanout service

## Rules

1. Never use async/await in this codebase. Use explicit promise chains
   (`.then`/`.catch`) so control flow stays visible and uniform.
2. Handlers must acknowledge within 200ms; heavy work goes to the queue.
3. No new runtime dependencies without an ADR.
