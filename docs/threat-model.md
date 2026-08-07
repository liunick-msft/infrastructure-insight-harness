# Threat Model

## Security Objective

Collect bounded infrastructure evidence without allowing a caller, AI client, or malformed configuration to turn the harness into a general remote-execution channel.

## Trust Boundaries

| Actor or asset | Trust assumption | Primary controls |
|---|---|---|
| Operator | Selects inventory, profile, host keys, and credentials | Explicit local configuration and preflight |
| Catalog maintainer | Contributed commands are safe and read-only | Review, strict schema, tests, device-side AAA |
| Caller or AI adapter | Untrusted beyond typed IDs | No command, credential, profile, or path inputs |
| Network and device | Network is hostile; device output may contain secrets | Strict host keys, timeouts, redaction, bounds |
| Credential store | Process environment is locally controlled | Named profiles, no logging or request inputs |
| Evidence store | Local filesystem may outlive a run | Disabled by default, explicit path, redacted writes |

## Threats and Mitigations

| Threat | Mitigation | Residual risk |
|---|---|---|
| Command injection | IDs resolve only to schema-validated, single-line `show ` commands | A vendor may implement a nominal `show` command with side effects; catalog review and read-only AAA remain required |
| Unauthorized breadth | Profile target/action budgets and required tags | An authorized action can still expose broad operational data |
| Host impersonation | Strict pinned SSH host-key verification | Initial fingerprint verification remains an operator responsibility |
| Credential disclosure | Environment-only credentials, no credential inputs or logs | Other privileged local processes may inspect environment variables |
| Secret-bearing output | Redaction before hashing, truncation, or persistence | Pattern-based redaction cannot prove removal of every secret format |
| Resource exhaustion | Sequential execution, command/target timeouts, bounded retry and output | Large valid fleets require deliberate profile changes and remain sequential |
| AI overclaiming | Collection state is separate from deterministic evaluation state | Consumers must preserve the result semantics |
| Policy bypass through MCP | Profile is local environment configuration, not a tool argument | A user who controls the local process environment controls its policy |

## Permanent Exclusions

Configuration writes, arbitrary commands, interactive shells, file transfer, tunnels, privilege escalation, caller-controlled safety overrides, and AI-generated commands reaching a transport are outside the product boundary.

## Validation Gaps

Live OS10 and NX-OS trials, adversarial catalog review, redaction corpus expansion, and clean-install CI remain required before a production claim.
