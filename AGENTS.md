# Infrastructure Insight Harness — Agent Instructions

This file provides structured instructions for AI agents (LLMs) to autonomously install, configure, and operate this tool. The tool collects read-only network device evidence over SSH.

## What This Tool Does

Connects to Cisco NX-OS and Dell OS10 switches via SSH, runs pre-approved read-only `show` commands, and returns structured JSON with the output. It cannot modify device configuration.

## Prerequisites (ask the operator for these)

| Required Input | Description | Example |
|---|---|---|
| Device IP or hostname | The management address of the target switch | `10.1.2.3` |
| Platform type | Either `os10` (Dell OS10) or `nxos` (Cisco NX-OS) | `os10` |
| SSH username | A read-only device account | `readonly` |
| SSH password | The password for that account | (operator provides) |
| SSH port | Default 22 unless non-standard | `22` |

## Installation

Installation is one-time per workstation. Skip this section if the tool is already installed.

### Check if already installed

```bash
# If this returns a help message, skip to "Setup Steps"
infrastructure-insight --help
```

On Windows PowerShell, also check:
```powershell
# If the venv exists, just activate it and skip install
if (Test-Path .\.venv\Scripts\Activate.ps1) { .\.venv\Scripts\Activate.ps1 }
infrastructure-insight --help
```

### First-time install (only if the check above fails)

```bash
git clone <REPO_URL> && cd infrastructure-insight-harness
python3 -m venv .venv
source .venv/bin/activate        # Linux/macOS
# OR on Windows PowerShell: .\.venv\Scripts\Activate.ps1
python3 -m pip install -e .
```

The venv and dependencies persist on disk. On subsequent sessions, only activate the venv:

```bash
cd infrastructure-insight-harness
source .venv/bin/activate        # Linux/macOS
# OR on Windows PowerShell: .\.venv\Scripts\Activate.ps1
```

## Setup Steps (run once per target device)

### Step 1: Create inventory file

Create `inventory.yaml` with one entry per device. Replace values with operator-provided inputs.

```yaml
version: 1
targets:
  - id: switch01
    address: 10.1.2.3
    platform: os10
    credential_profile: lab
    port: 22
    tags:
      - lab
```

Rules:
- `id` must be lowercase alphanumeric with hyphens/underscores, max 64 chars.
- `platform` must be exactly `os10` or `nxos`.
- `credential_profile` determines which environment variables supply credentials (see Step 3).
- Include `lab` in `tags` — the `lab` and `audit` profiles require this tag.

### Step 2: Pin SSH host key

This step is mandatory and cannot be skipped. The tool enforces strict host-key verification.

```bash
ssh-keyscan -T 5 -p 22 <DEVICE_IP> 2>/dev/null > known_hosts
```

On Windows PowerShell:
```powershell
ssh-keyscan -T 5 -p 22 <DEVICE_IP> 2>$null | Set-Content -Encoding ascii .\known_hosts
```

If connecting to multiple devices, append:
```bash
ssh-keyscan -T 5 -p 22 <SECOND_DEVICE_IP> 2>/dev/null >> known_hosts
```

### Step 3: Set credentials as environment variables

The credential environment variables follow the pattern: `IIH_<PROFILE>_USERNAME` and `IIH_<PROFILE>_PASSWORD` where `<PROFILE>` is the uppercase `credential_profile` from the inventory.

For `credential_profile: lab`:

```bash
export IIH_LAB_USERNAME="<username>"
export IIH_LAB_PASSWORD="<password>"
```

On Windows PowerShell:
```powershell
$env:IIH_LAB_USERNAME = "<username>"
$env:IIH_LAB_PASSWORD = "<password>"
```

## Available Actions

These are the pre-approved commands the tool can run. You select them by ID.

| Action ID | Description | Sensitive | Platform Commands |
|---|---|---|---|
| `platform_version` | Collect platform model, software version, uptime | No | NX-OS: `show version`, OS10: `show version` |
| `interface_status` | Collect interface admin/operational status | No | NX-OS: `show interface status`, OS10: `show interface status` |
| `lldp_neighbors` | Collect discovered LLDP neighbors | No | NX-OS: `show lldp neighbors`, OS10: `show lldp neighbors` |
| `bgp_summary` | Collect IPv4 BGP neighbor summary | No | NX-OS: `show bgp ipv4 unicast summary`, OS10: `show ip bgp summary` |
| `running_configuration` | Collect full running config | **Yes** | NX-OS: `show running-config`, OS10: `show running-configuration` |
| `bgp_configuration` | Collect BGP config section only | **Yes** | NX-OS: `show running-config section "^router bgp"`, OS10: `show running-configuration bgp` |

## Available Profiles

Profiles control how many targets/actions are allowed per run.

| Profile | Max Targets | Max Actions | Sensitive Allowed | Evidence Persistence |
|---|---|---|---|---|
| `cautious` (default) | 1 | 5 | No | No |
| `lab` | 8 | 10 | No | Yes |
| `audit` | 1 | 3 | **Yes** | Yes |

## Running Commands

### Preflight check (validates setup without SSH connection)

```bash
infrastructure-insight --inventory ./inventory.yaml \
    --known-hosts ./known_hosts preflight --targets switch01
```

Expected success output:
```json
[{"target_id": "switch01", "credential_available": true, "host_key_pinned": true, "ready": true}]
```

If `ready` is `false`, check which field is `false`:
- `credential_available: false` → environment variables not set or wrong profile name
- `host_key_pinned: false` → host key not in known_hosts file or wrong IP/port

### Collect non-sensitive evidence (default cautious profile)

```bash
infrastructure-insight --inventory ./inventory.yaml \
    --known-hosts ./known_hosts run \
    --targets switch01 \
    --actions platform_version interface_status bgp_summary
```

### Collect sensitive evidence (requires audit profile)

```bash
infrastructure-insight --inventory ./inventory.yaml \
    --known-hosts ./known_hosts \
    --profile audit \
    --evidence-dir ./evidence run \
    --targets switch01 \
    --actions running_configuration
```

### Collect from multiple targets (requires lab profile)

```bash
infrastructure-insight --inventory ./inventory.yaml \
    --known-hosts ./known_hosts \
    --profile lab run \
    --targets switch01 switch02 \
    --actions bgp_summary lldp_neighbors
```

### List available targets

```bash
infrastructure-insight --inventory ./inventory.yaml \
    --known-hosts ./known_hosts list-targets
```

### List available actions

```bash
infrastructure-insight --inventory ./inventory.yaml \
    --known-hosts ./known_hosts list-actions
```

## Interpreting Results

The tool returns JSON. Key fields:

```json
{
  "started_at": "ISO timestamp",
  "completed_at": "ISO timestamp",
  "results": [
    {
      "target_id": "switch01",
      "action_id": "bgp_summary",
      "collection_state": "success | transport_error | authentication_error | timeout | cli_error | policy_error",
      "validation_state": "unknown",
      "output": "the device output (redacted, bounded)",
      "byte_count": 1234,
      "sha256": "hash of redacted output",
      "truncated": false,
      "error": null
    }
  ]
}
```

### collection_state meanings

| State | Meaning | Agent Action |
|---|---|---|
| `success` | Device output collected | Parse the `output` field |
| `transport_error` | SSH connection failed | Check network reachability, verify known_hosts |
| `authentication_error` | Login rejected | Verify IIH_<PROFILE>_USERNAME and PASSWORD env vars |
| `timeout` | Device did not respond in time | Device may be overloaded; retry later |
| `cli_error` | Device returned an error to the command | The command may not be supported on this device/version |
| `policy_error` | Request violated profile constraints | Check profile limits (target count, action count, sensitive) |

### validation_state

Always `unknown`. This field is reserved for future deterministic evaluators. The agent should interpret the raw `output` directly.

## Error Handling

| Error | Cause | Fix |
|---|---|---|
| `unknown target: X` | Target ID not in inventory file | Check spelling matches inventory `id` field |
| `unknown action: X` | Action ID not in catalog | Use only the action IDs listed in Available Actions above |
| `profile permits at most N targets` | Too many targets for selected profile | Switch to `lab` profile or reduce target count |
| `does not permit sensitive actions` | Used sensitive action with cautious/lab profile | Switch to `audit` profile |
| `credential profile 'X' is incomplete` | Missing environment variables | Set both IIH_<PROFILE>_USERNAME and IIH_<PROFILE>_PASSWORD |
| `known-hosts file does not exist` | Path to known_hosts is wrong | Verify --known-hosts path |
| `missing profile-required tags` | Target lacks required tag | Add `lab` tag to target in inventory |

## CLI Exit Codes

| Code | Meaning |
|---|---|
| 0 | All actions collected successfully |
| 1 | Some actions failed (partial results in JSON output) |
| 2 | Setup/validation error before execution (error in stderr) |

## Security Constraints (cannot be bypassed)

- Only pre-approved `show` commands from the catalog can be executed.
- No arbitrary commands, configuration changes, or interactive shells.
- SSH host-key verification is always strict — no way to disable.
- Credentials come only from environment variables — never from CLI args or files.
- Output is automatically redacted (passwords, SNMP communities, secrets replaced with `<redacted>`).
- Output is bounded to the profile's `max_inline_bytes` limit.

## Multi-Device Inventory Example

```yaml
version: 1
targets:
  - id: spine01
    address: 10.0.1.1
    platform: nxos
    credential_profile: lab
    tags:
      - lab
  - id: leaf01
    address: 10.0.1.10
    platform: os10
    credential_profile: lab
    tags:
      - lab
  - id: leaf02
    address: 10.0.1.11
    platform: os10
    credential_profile: lab
    tags:
      - lab
```

All three devices use `credential_profile: lab`, so they share the same `IIH_LAB_USERNAME` / `IIH_LAB_PASSWORD` environment variables. To use different credentials per device, assign different `credential_profile` values and set the corresponding environment variables.

## Windows PowerShell Equivalents

All bash commands above work on Windows PowerShell with these substitutions:

| Bash | PowerShell |
|---|---|
| `source .venv/bin/activate` | `.\.venv\Scripts\Activate.ps1` |
| `export VAR="value"` | `$env:VAR = "value"` |
| `./path` | `.\path` |
| `\` (line continuation) | `` ` `` (backtick) |
| `2>/dev/null` | `2>$null` |
| `python3` | `python` |
