# Gemini instructions

- <!-- PYLGRIM-CONFLICT-01 --> Use yarn for all installs and scripts; npm lockfiles must not be committed.
- All configuration is read from `config/app.json`; never hardcode a config value in source.
- Message payloads are treated as opaque bytes; never parse a payload outside `src/codec.js`.
