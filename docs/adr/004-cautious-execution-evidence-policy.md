# ADR-004: Cautious Execution and Evidence Policy

## Status

Accepted on 2026-08-07.

## Decision

Every run is authorized by a locally selected, operator-owned execution profile before credentials or network access. Profiles bound target count, actions per target, required target tags, sensitive actions, timeouts, retry count, login pacing, inline evidence, and persistence.

The default cautious profile permits one target, five actions, no sensitive actions, one transient retry, and no evidence persistence. Persistence requires both a profile that permits it and an explicit local evidence directory.

## Rationale

Sequential execution limits concurrency but not total blast radius. Descriptive sensitivity labels and implicit evidence directories do not enforce safety. These controls must be deterministic policy rather than caller judgment.

## Consequences

- Over-budget, wrongly tagged, and sensitive requests fail before transport creation.
- MCP callers cannot choose a more permissive profile.
- Redaction occurs before hashing, truncation, or persistence.
- The evidence hash identifies redacted bytes, not raw device output.
- Profiles never disable catalog authorization, strict host keys, redaction, or evidence bounds.
