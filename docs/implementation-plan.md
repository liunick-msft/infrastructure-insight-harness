# Infrastructure Insight Harness Implementation Plan

## Mission

Provide a reusable, policy-constrained harness that safely collects and eventually evaluates infrastructure evidence across Cisco NX-OS and Dell OS10 without allowing arbitrary commands or configuration changes.

```text
CLI or optional MCP request
    -> operator-owned execution profile
    -> validated inventory and contributed action IDs
    -> sequential executor
    -> platform command resolver
    -> strict SSH
    -> bounded evidence and truthful result
```

## Milestone Tracker

| Milestone | Status | Completion Gate | Evidence |
|---|---|---|---|
| 0. Product contract | Complete | Harness naming, permanent exclusions, threat model, and ADRs agree | Contract and architecture docs updated |
| 1. Installable CLI evidence slice | Implemented; live validation pending | Clean core install, packaged policy, strict SSH, partial results | Unit tests and clean wheel build pass |
| 2. Execution policy and semantics | Implemented; evaluator pending | Enforced cardinality, tags, sensitivity, retry, timeout, and persistence policy | Focused policy tests pass; collection remains distinct from evaluation |
| 3. Live validation and publication controls | In progress | OS10/NX-OS trial, CI, governance, license, clean-install smoke test | CI/governance added; device trial and license pending |
| 4. Optional MCP adapter | Implemented locally; release follows Milestone 3 | Four bounded tools with no profile, command, credential, or evidence-path authority | In-memory MCP schema test passes |
| 5. Next capability decision | Not started | Evidence-backed ADR selects one measured investment | Pending |

## Current Secure Slice

### Deliverables

- Minimal target, action, request, and result models.
- Versioned YAML inventory and action catalog.
- Four contributed cross-platform validation actions: platform/version, interface status, LLDP neighbors, and BGP summary.
- One explicit sensitive action that default profiles deny.
- Fail-closed command template and typed parameter validation.
- Strict Netmiko SSH with hard timeouts, deterministic cleanup, one bounded retry, and login pacing.
- Sequential execution across targets with per-action partial results.
- Bounded output with optional local evidence, timestamp, byte count, hash, and truncation state.
- CLI as the primary product interface and MCP as an optional adapter.

### Exit Test

Run the same action IDs against one NX-OS and one OS10 target, deliberately make one target unreachable, and attempt unknown, injected, sensitive, and over-budget requests. The milestone fails if vendor resolution is wrong, one failure erases another result, host trust can be bypassed, or unauthorized input reaches SSH.

Field validation findings and proposed transport-boundary improvements are
recorded in [Field Validation Feedback](field-validation-feedback.md).

## Deferred

- Production Redfish support
- Generic adapter framework
- Cache and offline analysis
- Parallel execution and session pooling
- Broad parser framework
- Multiple credential backends
- Hosted MCP transports

## Decision Records

- [ADR-001: Read-only catalog authorization](adr/001-read-only-catalog.md)
- [ADR-002: Local stdio and direct SSH](adr/002-local-stdio-direct-ssh.md)
- [ADR-003: CLI-primary harness with optional MCP](adr/003-cli-primary-optional-mcp.md)
- [ADR-004: Cautious execution and evidence policy](adr/004-cautious-execution-evidence-policy.md)
