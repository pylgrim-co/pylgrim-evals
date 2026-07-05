# orderly: invoice service

Guidance for agents and humans working in this repo.

## Rules

1. Never edit files under `src/gen/`. They are generated from the OpenAPI spec; change the spec and run `npm run codegen`.
2. Route handlers never touch the database client directly. All data access goes through `src/services/`; routes stay thin.
3. Money is always integer cents stored as `bigint`. Never represent money as a float, anywhere, including tests.
4. Every new public function in `src/services/` gets a test in `tests/` in the same PR.
5. Migrations are append-only: never edit an existing file under `src/db/migrations/`. Fixing a bad migration means writing a new one.
6. Request validation uses the zod schemas in `src/schemas.ts`. No hand-rolled validation in routes or services.
7. Log through `src/lib/logger.ts` only. `console.log` is allowed in tests and nowhere else.
8. Outbound HTTP calls go through `src/lib/http.ts`, which enforces a 5 second timeout. Never call fetch directly.
