# ADR 0001: Postgres over MySQL

Status: accepted, 2025-11-03

## Decision

We use PostgreSQL as the only database.

## Why

We need transactional DDL for the append-only migration scheme and `bigint`
money columns with strict overflow behavior. The team already operates
Postgres in two other products, so the operational cost is sunk.

## Consequences

All migrations are plain SQL files under src/db/migrations/, applied in
lexical order, never edited after merge.
