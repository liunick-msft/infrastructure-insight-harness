# Field Validation Feedback

This note records reusable functional and architectural findings from an
operator-led validation. It intentionally excludes target identifiers,
addresses, credentials, configuration content, and platform-specific details.

## Confirmed Improvement

### Persist evidence whenever persistence is explicitly enabled

An evidence directory is accepted only when the selected execution profile
permits persistence. Once both gates are satisfied, the complete redacted
output should be written even when it fits within the inline response limit.
Truncation controls the inline representation; it should not control whether
approved persistence occurs.

## Functional Suggestions

### Expose the complete transport command plan

Some SSH libraries prepare interactive sessions by sending commands before the
catalog action. Those commands are not currently visible in the action catalog
or run result. Add a transport command plan that includes every command which
can reach a target, including session preparation. Validate that plan against
an operator-owned allowlist before opening SSH.

This preserves the claim that network authority is deterministic and
reviewable. A transport adapter should either send no implicit commands or
declare each required setup command as part of its contributed capability.

### Add a no-connect execution-plan command

Extend preflight with a mode that reports the selected targets, action IDs,
resolved catalog commands, transport setup operations, profile limits, and
evidence behavior without resolving secret values or opening a connection.
This gives operators a precise approval artifact before execution.

### Normalize transport diagnostics

Transport implementations can return informational login or session messages
separately from command output. Model command output, diagnostic output, and
exit status as distinct fields. Classify failure from explicit status and known
protocol signals rather than assuming that any diagnostic text is an error.
Diagnostic content should remain bounded and redacted.

### Make credential providers injectable at the service boundary

The runner already depends on a credential-provider protocol, while the
application service constructs one concrete environment provider. Move provider
selection behind an application-level factory so local prompt, operating-system
credential store, and automation providers can be added without changing CLI or
MCP request authority. Secret values must remain out of inventories, arguments,
results, and logs.

## Design And Structure Suggestions

### Separate transport policy from transport mechanics

Split transport responsibilities into three explicit boundaries:

1. A transport plan describes connection and session setup operations.
2. A transport policy authorizes the complete plan before network access.
3. A transport adapter executes only the authorized plan and returns a
   normalized result.

This keeps library-specific session behavior from bypassing the catalog's
review boundary and allows future adapters to share the same policy tests.

### Add live contract smoke tests

Unit tests prove policy and result handling but cannot prove interactive SSH
behavior. Add opt-in smoke tests against disposable targets that capture the
commands observed by the endpoint and assert that they exactly match the
authorized transport plan. Keep these tests outside default CI unless an
isolated test target and ephemeral credentials are available.

### Keep field fixtures synthetic

Regression fixtures should contain generated identifiers, documentation-range
addresses, and synthetic command output. Validation reports should record only
result classifications, byte counts, hashes of redacted evidence, and the
commands authorized by the plan.
