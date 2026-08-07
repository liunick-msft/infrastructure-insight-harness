# ADR-003: CLI-Primary Harness with Optional MCP

## Status

Accepted on 2026-08-07.

## Decision

Infrastructure Insight Harness is a transport-neutral application service with a primary CLI and an optional local Model Context Protocol (MCP) adapter. MCP is an integration surface, not the product identity or authorization boundary.

Both interfaces accept contributed target and action IDs only. The MCP adapter cannot select an execution profile, evidence path, credential, command, or safety override.

## Rationale

The reusable value is deterministic policy around infrastructure access: reviewed actions, strict host trust, credential isolation, execution limits, evidence handling, and truthful results. A local operator benefits from those controls without installing an AI protocol dependency.

## Consequences

- Core installation does not require the MCP SDK.
- CLI and MCP call the same service and produce the same result model.
- Protocol-specific code remains thin and optional.
- New adapters cannot expand harness authority.
