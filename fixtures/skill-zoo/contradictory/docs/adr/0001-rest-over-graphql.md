# ADR 0001: REST over GraphQL

Status: accepted, 2025-09-02

## Decision

The public API is REST. We explicitly rejected GraphQL.

## Why

Webhook consumers are simple server-side integrations; REST with static
docs is enough, and the team has no GraphQL operations experience.

## Consequences

All new endpoints are REST routes under src/api/.
