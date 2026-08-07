# Contributing

Infrastructure Insight Harness accepts focused changes that preserve its permanent read-only and contributed-action boundaries.

## Development Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pytest
```

## Contribution Requirements

- Keep the CLI primary and MCP optional.
- Never add arbitrary command, credential, shell, URI, file-transfer, tunnel, configuration, or safety-override inputs.
- Reject invalid requests before credentials or network access.
- Preserve strict SSH host-key verification, sequential execution, bounded retry, redaction, evidence limits, and partial results.
- Add focused tests for security boundaries and failure classification.
- Do not include real hostnames, addresses, credentials, logs, customer identifiers, or internal URLs.
- Update decision records when a change alters a permanent boundary or architectural tradeoff.

## Contributed Actions

An action must have a stable lowercase ID, a bounded description, and an explicit command for every supported platform. Commands must be single-line `show ` commands with no pipes, redirects, separators, parameters, or templates. Mark actions sensitive when their output can reveal configuration or identity data.

A `show ` prefix is necessary but not sufficient proof of safety. Review vendor behavior and require a device-side read-only AAA account. New sensitive actions must remain denied until an execution profile explicitly permits them and tests prove the gate.

## Pull Request Evidence

Include the behavior changed, security impact, tests run, and any live-device evidence or remaining validation gap. Do not claim device support from unit tests alone.

## Publication Status

A license and maintainer publication details have not yet been selected. External contributions cannot be accepted until those governance decisions are complete.
