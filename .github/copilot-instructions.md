# Repository Instructions

## Quick Reference

- For **operating this tool** (install, configure, run commands): read `AGENTS.md` at repo root.
- For **developing this tool** (code changes, architecture, security): read this file and `docs/`.

## Product Invariants

- This product is permanently read-only.
- The CLI is the primary interface. MCP is an optional adapter and never expands authority.
- Never add arbitrary command, shell, script, URI, HTTP method, credential, configuration, upload, tunnel, or privilege inputs to any interface.
- Only version-controlled catalog actions may reach a transport.
- Execution profiles are operator-owned policy and are never request-controlled through MCP.
- Reject invalid policy and requests before network access.
- Require strict SSH host-key verification.
- Keep credentials and raw device output out of logs.
- Keep evidence persistence disabled unless local policy permits it and the operator supplies a directory.
- Report collection state separately from validation state.
- Preserve partial results when one target fails.

## Engineering

- Keep the initial architecture small: models, inventory, catalog, platform resolvers, SSH transport, and sequential runner.
- Add abstractions only after a second implementation or measured operational need exists.
- Use Pydantic for external configuration and request validation.
- Add focused tests for every security boundary and failure mode.
- Update `docs/implementation-plan.md` with evidence when milestone status changes.

## Official MCP References

- Python SDK: https://github.com/modelcontextprotocol/python-sdk
- Python SDK documentation: https://py.sdk.modelcontextprotocol.io/
- MCP specification and documentation corpus: https://modelcontextprotocol.io/llms-full.txt
