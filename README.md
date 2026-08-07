# Infrastructure Insight Harness

Infrastructure Insight Harness is a configurable, policy-constrained harness for collecting and evaluating infrastructure evidence. It gives operators and AI clients the same deterministic safety boundary: contributed targets, contributed read-only actions, strict host trust, bounded execution, redacted evidence, and truthful results.

The initial transport supports Cisco NX-OS and Dell OS10 over SSH. The CLI is the primary interface; Model Context Protocol (MCP) integration is optional.

> [!WARNING]
> This project is under active development and has not completed live device validation or selected a publication license. It is not yet a production release or licensed for redistribution.

## Permanent Non-Goals

- Configuration changes, staging, or saving.
- Arbitrary commands or AI-generated commands reaching a device.
- Interactive shells, file transfer, tunnels, or privilege escalation.
- Caller-controlled safety overrides.
- Treating successful evidence collection as a passed validation.

## Architecture

```text
Human or script                 AI client
			|                             |
			v                             v
		 CLI                    Optional MCP adapter
			|                             |
			+-------------+---------------+
										|
					 Application service
										|
			 Inventory + action catalog + execution profile
										|
					 Sequential SSH executor
										|
					Redact -> bound -> hash -> report
										|
				Optional deterministic evaluation
```

MCP does not grant additional authority. Both interfaces call the same application service, and callers can select only target and action IDs.

## Why Use It

- Review infrastructure access as data and policy instead of free-form scripts.
- Preserve useful results when one target or action fails.
- Apply the same limits to a human operator, automation, or probabilistic AI.
- Produce bounded, attributable evidence without logging credentials or raw secrets.
- Add deterministic assertions later without allowing AI inference to become pass/fail truth.

## CLI Quick Start

### PowerShell (Windows)

Use Python 3.10 or later from PowerShell.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

1. Copy and edit the documentation-safe inventory example. Use a device-side read-only AAA account and add `lab` only to targets intentionally eligible for the lab profile.
2. Acquire each SSH host key and independently verify its fingerprint through a trusted channel.

```powershell
ssh-keyscan -T 5 -p 22 192.0.2.10 2>$null | Set-Content -Encoding ascii .\known_hosts
ssh-keygen -lf .\known_hosts
```

`ssh-keyscan` retrieves a key but does not authenticate it. Do not continue until its fingerprint matches a trusted device or administrator record.

3. Put credentials only in the current process environment.

```powershell
$credential = Get-Credential
$env:IIH_LAB_USERNAME = $credential.UserName
$env:IIH_LAB_PASSWORD = $credential.GetNetworkCredential().Password
```

4. Check credentials and pinned host keys without opening SSH.

```powershell
infrastructure-insight --inventory .\examples\inventory.yaml `
	--known-hosts .\known_hosts preflight --targets os10-leaf01
```

5. Run contributed non-sensitive actions under the default cautious profile.

```powershell
infrastructure-insight --inventory .\examples\inventory.yaml `
	--known-hosts .\known_hosts run `
	--targets os10-leaf01 `
	--actions platform_version interface_status lldp_neighbors bgp_summary
```

### Bash (Linux / macOS)

Use Python 3.10 or later.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .
```

1. Copy and edit the inventory example. Use a device-side read-only AAA account and add `lab` only to targets intentionally eligible for the lab profile.

```bash
cp examples/inventory.yaml my-inventory.yaml
# Edit my-inventory.yaml with your target addresses and platform types
```

2. Acquire each SSH host key and independently verify its fingerprint through a trusted channel.

```bash
ssh-keyscan -T 5 -p 22 192.0.2.10 2>/dev/null > known_hosts
ssh-keygen -lf known_hosts
```

`ssh-keyscan` retrieves a key but does not authenticate it. Do not continue until its fingerprint matches a trusted device or administrator record.

3. Put credentials only in the current process environment.

```bash
read -p "Username: " IIH_LAB_USERNAME && export IIH_LAB_USERNAME
read -sp "Password: " IIH_LAB_PASSWORD && export IIH_LAB_PASSWORD && echo
```

4. Check credentials and pinned host keys without opening SSH.

```bash
infrastructure-insight --inventory ./examples/inventory.yaml \
    --known-hosts ./known_hosts preflight --targets os10-leaf01
```

5. Run contributed non-sensitive actions under the default cautious profile.

```bash
infrastructure-insight --inventory ./examples/inventory.yaml \
    --known-hosts ./known_hosts run \
    --targets os10-leaf01 \
    --actions platform_version interface_status lldp_neighbors bgp_summary
```

## Use Cases

### Use Case 1: Pull Full Device Configuration

Collect the full running configuration from a device for offline review or audit. The `running_configuration` action is marked sensitive because device configs contain credentials, so it requires the `audit` profile.

**PowerShell:**

```powershell
# Use the audit profile (allows sensitive actions) and persist evidence to disk
infrastructure-insight --inventory .\examples\inventory.yaml `
    --known-hosts .\known_hosts `
    --profile audit `
    --evidence-dir .\evidence run `
    --targets os10-leaf01 `
    --actions running_configuration
```

**Bash:**

```bash
infrastructure-insight --inventory ./examples/inventory.yaml \
    --known-hosts ./known_hosts \
    --profile audit \
    --evidence-dir ./evidence run \
    --targets os10-leaf01 \
    --actions running_configuration
```

The harness redacts known secret patterns (passwords, SNMP communities, authentication keys) before hashing or persisting. The output JSON reports `collection_state`, a SHA-256 hash of the redacted content, byte count, and whether the inline output was truncated. When `--evidence-dir` is set and the profile permits persistence, the full redacted output is also written to the evidence directory.

> [!NOTE]
> The `cautious` and `lab` profiles both deny sensitive actions. The `audit` profile allows sensitive actions but limits scope to one `lab`-tagged target and at most three actions per run.

### Use Case 2: Validate BGP Neighbor Status

Collect the BGP summary from one or more devices to verify that expected peers are established. The `bgp_summary` action is non-sensitive and works under the default `cautious` profile.

**PowerShell:**

```powershell
infrastructure-insight --inventory .\examples\inventory.yaml `
    --known-hosts .\known_hosts run `
    --targets os10-leaf01 `
    --actions bgp_summary
```

**Bash:**

```bash
infrastructure-insight --inventory ./examples/inventory.yaml \
    --known-hosts ./known_hosts run \
    --targets os10-leaf01 \
    --actions bgp_summary
```

Example output (trimmed):

```json
{
  "started_at": "2026-08-07T18:30:00Z",
  "completed_at": "2026-08-07T18:30:05Z",
  "results": [
    {
      "target_id": "os10-leaf01",
      "action_id": "bgp_summary",
      "collection_state": "success",
      "validation_state": "unknown",
      "output": "BGP router identifier 10.0.0.1, local AS number 65001\nNeighbor   AS   MsgRcvd  MsgSent  Up/Down  State/PfxRcd\n10.0.0.2   65002  1024     1020     2d03h    12\n10.0.0.3   65003  980      975      1d22h    8\n",
      "byte_count": 210,
      "sha256": "a1b2c3...",
      "truncated": false
    }
  ]
}
```

To check multiple devices under the `lab` profile (which allows up to eight `lab`-tagged targets):

**PowerShell:**

```powershell
infrastructure-insight --inventory .\examples\inventory.yaml `
    --known-hosts .\known_hosts `
    --profile lab run `
    --targets os10-leaf01 nxos-leaf01 `
    --actions bgp_summary
```

**Bash:**

```bash
infrastructure-insight --inventory ./examples/inventory.yaml \
    --known-hosts ./known_hosts \
    --profile lab run \
    --targets os10-leaf01 nxos-leaf01 \
    --actions bgp_summary
```

The `collection_state` tells you whether data was obtained. `validation_state` remains `unknown` because no deterministic evaluator is contributed yet — the operator interprets the BGP output to confirm peer state. If one target is unreachable, its result shows `transport_error` or `timeout` while the other target's results are preserved.

## Configuration

The operator owns the inventory and selected execution profile. The package supplies reviewed default actions and profiles; either can be replaced with an explicit file.

| Input | CLI option | MCP environment | Default |
|---|---|---|---|
| Inventory | `--inventory` | `IIH_INVENTORY` | Required |
| Action catalog | `--catalog` | `IIH_CATALOG` | Packaged catalog |
| Profile catalog | `--profiles` | `IIH_PROFILES` | Packaged profiles |
| Selected profile | `--profile` | `IIH_PROFILE` | `cautious` |
| Known hosts | `--known-hosts` | `IIH_KNOWN_HOSTS` | User SSH known-hosts |
| Evidence directory | `--evidence-dir` | `IIH_EVIDENCE_DIR` | Disabled |

The cautious profile allows one target, at most five actions, no sensitive actions, sequential execution, one transient retry, and no evidence files. The lab profile allows up to eight `lab`-tagged targets and ten actions. The audit profile allows one `lab`-tagged target and up to three actions including sensitive actions such as `running_configuration`, with evidence persistence and a higher inline-byte limit. Lab and audit still cannot bypass catalog authorization, strict host keys, redaction, timeouts, or evidence bounds. Evidence files require both a profile that permits persistence and an explicit directory.

## Result Semantics

`collection_state` says whether evidence was obtained or why collection failed. `validation_state` remains `unknown` until a contributed deterministic evaluator produces a result. AI can explain evidence, but it cannot manufacture a pass or fail.

The SHA-256 value covers the redacted evidence bytes, not the raw device response. Inline output is bounded; optional persisted output is redacted before it is written.

## Optional MCP Adapter

Install the extra and set operator-owned environment before starting VS Code.

**PowerShell:**

```powershell
python -m pip install -e ".[mcp]"
$env:IIH_INVENTORY = (Resolve-Path .\examples\inventory.yaml)
$env:IIH_KNOWN_HOSTS = (Resolve-Path .\known_hosts)
code .
```

**Bash:**

```bash
python3 -m pip install -e ".[mcp]"
export IIH_INVENTORY="$(realpath ./examples/inventory.yaml)"
export IIH_KNOWN_HOSTS="$(realpath ./known_hosts)"
code .
```

The adapter exposes only `insight_list_targets`, `insight_list_actions`, `insight_preflight`, and `insight_run`. Profile selection and evidence paths are not MCP tool inputs.

## Security and Contribution Status

Read [docs/threat-model.md](docs/threat-model.md), [SECURITY.md](SECURITY.md), and [CONTRIBUTING.md](CONTRIBUTING.md) before deploying or contributing actions. CI and dependency update configuration are included.

## AI Agent Usage

For LLM or AI agent integration, see [AGENTS.md](AGENTS.md) for structured, machine-parseable setup and operation instructions.

For development validation:

**PowerShell:**

```powershell
python -m pip install -e ".[dev]"
python -m pytest
python -m build --wheel
```

**Bash:**

```bash
python3 -m pip install -e ".[dev]"
python3 -m pytest
python3 -m build --wheel
```

See [docs/implementation-plan.md](docs/implementation-plan.md) for milestone status and exit evidence.
