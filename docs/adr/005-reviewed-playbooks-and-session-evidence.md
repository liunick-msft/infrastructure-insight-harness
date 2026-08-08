# ADR-005: Reviewed Playbooks and Session Evidence

## Status

Accepted on 2026-08-07.

## Decision

Diagnostic workflows are declarative reviewed playbooks containing action IDs, supported platforms, and actions covered by broader evidence. Playbooks never contain commands. The action catalog remains the sole command authority.

Operators can preview an authorized endpoint-bound plan before execution. Its SHA-256 digest covers the playbook and catalog versions, selected profile, target ID, address, port, platform, action metadata, and exact commands. Planning does not access credentials, host keys, or transport.

Persistence-enabled profiles create a unique session directory under an explicit evidence root or the system temporary directory. The directory is restricted to the current user. Successful actions persist exact raw output and redacted output; a manifest records exact commands, collection states, paths, byte counts, and both hashes. Credentials and authentication exchanges are never evidence.

## Rationale

Diagnostics require repeatable evidence sets without allowing callers or AI to compose commands. Broad evidence such as full running configuration should satisfy narrower configuration needs without a duplicate device command. Exact raw output is required for future parsing and forensic review, while API output remains bounded and redacted.

## Consequences

- Unknown, unsupported, over-budget, wrongly tagged, and sensitive playbook requests fail before network access.
- Direct requests still reject duplicate IDs; playbook expansion removes repeated action IDs while preserving first occurrence.
- Raw evidence is intentionally sensitive and may contain secrets not recognized by redaction patterns.
- Failure to create or secure a session directory aborts execution before credentials are read.
- The initial `bgp_health` playbook supports OS10 only and collects evidence without producing health findings.
- The earlier ADR-004 requirement for an explicit persistence path is superseded by the secured temporary-directory fallback in this decision.
