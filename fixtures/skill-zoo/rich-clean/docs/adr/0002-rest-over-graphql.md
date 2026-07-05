# ADR 0002: REST over GraphQL

Status: accepted, 2025-11-19

## Decision

The public API is REST, defined in an OpenAPI spec, with generated types
under src/gen/.

## Why

Invoicing clients are server-to-server integrations that want stable,
versioned endpoints and generated clients. Nobody asked for query
flexibility; everybody asked for a changelog.

## Consequences

src/gen/ is generated output: never hand-edited, regenerated with
`npm run codegen` whenever openapi.yaml changes.
