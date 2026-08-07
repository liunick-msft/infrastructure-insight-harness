# ADR-002: Local Execution and Direct SSH

## Status

Accepted on 2026-08-07.

## Decision

The initial harness runs locally and connects directly to switches using strict SSH host-key verification. The CLI is primary; an optional MCP adapter uses local standard input/output. Execution is sequential and opens one connection per target per request.

## Rationale

This is the smallest deployment that tests command authorization, vendor behavior, authentication, timeout handling, and partial failures against real devices.

## Consequences

- No cloud service, relay, database, hosted protocol transport, concurrency, or connection pool is required.
- A one-hop jumpbox and Redfish remain deferred until evidence establishes their need.
