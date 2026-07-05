# ADR 0003: zod for request validation

Status: accepted, 2026-01-12

## Decision

All request payloads are validated with zod schemas defined in
src/schemas.ts, shared between routes and tests.

## Why

One schema definition drives runtime validation and static types, so
validation cannot drift from the type system. Hand-rolled checks kept
missing edge cases (empty strings, negative cents).

## Consequences

New endpoints add a schema to src/schemas.ts first; routes refuse
anything the schema rejects with a 422.
