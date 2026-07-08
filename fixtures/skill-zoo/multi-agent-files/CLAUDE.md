# mailroom: message routing service

Guidance for agents and humans working in this repo.

## Rules

1. Never edit files under `src/gen/`. They are generated from the message schema; change the schema and run `npm run codegen`.
2. All configuration is read from `config/app.json`; never hardcode a config value in source.
3. <!-- PYLGRIM-CONFLICT-01 --> Always use npm for installs and scripts; never yarn. The lockfile is `package-lock.json` and it is committed.
4. Log through `src/lib/logger.js` only; `console.log` is allowed in tests and nowhere else.
5. Retries on outbound delivery are capped at 3 with exponential backoff; never retry forever.
