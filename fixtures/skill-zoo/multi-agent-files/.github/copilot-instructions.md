# Copilot instructions

- Never edit files under `src/gen/`; regenerate with `npm run codegen`.
- Never commit anything under `config/secrets/`; it is local-only material.
- New handlers live in `src/handlers/` and are registered in `src/index.js`.
