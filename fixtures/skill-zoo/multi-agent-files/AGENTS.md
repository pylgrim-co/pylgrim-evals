# Agent notes

- Never edit files under `src/gen/`; they are generated output. Change the schema and run `npm run codegen`.
- <!-- PYLGRIM-CONFLICT-02 --> All data access goes through the repository layer in `src/db/repo.js`. Handlers must never import the ORM directly.
- Run `npm test` before declaring any task done.
- Keep PRs small: one handler or one repository change at a time.
