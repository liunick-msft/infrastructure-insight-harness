# ADR-001: Read-Only Catalog Authorization

## Status

Accepted on 2026-08-07.

## Decision

Only version-controlled action IDs resolve to executable commands. Callers cannot submit raw commands or credentials. Configuration mutation, staging, saving, file transfer, tunneling, and interactive sessions are permanently excluded.

## Rationale

The important safety boundary is deterministic server authorization, not model judgment. A contributed catalog is reviewable, testable, and deny-by-default.

## Consequences

- Adding a command requires a reviewed catalog change and tests.
- Unknown actions fail before network access.
- Device-side read-only AAA remains defense in depth.
