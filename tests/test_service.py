from pathlib import Path

from paramiko import RSAKey
from paramiko.hostkeys import HostKeys

from infrastructure_insight.cli import build_parser
from infrastructure_insight.models import RunRequest
from infrastructure_insight.policy import PolicyError
from infrastructure_insight.service import InsightService, RuntimePaths


def test_cli_has_no_raw_command_argument() -> None:
    help_text = build_parser().format_help()

    assert "--command" not in help_text


def test_service_lists_actions_without_command_text(tmp_path: Path) -> None:
    inventory = tmp_path / "inventory.yaml"
    inventory.write_text(
        """
version: 1
targets:
  - id: leaf01
    address: 192.0.2.10
    platform: os10
    credential_profile: lab
""",
        encoding="utf-8",
    )
    catalog = tmp_path / "actions.yaml"
    catalog.write_text(
        """
version: 1
actions:
  platform_version:
    description: Show platform version
    commands:
      nxos: show version
      os10: show version
""",
        encoding="utf-8",
    )
    service = InsightService(
        RuntimePaths(
            inventory=inventory,
            catalog=catalog,
            known_hosts=tmp_path / "known_hosts",
            evidence_dir=None,
        )
    )

    actions = service.list_actions()

    assert actions == [
        {
            "id": "platform_version",
            "description": "Show platform version",
            "sensitive": False,
            "platforms": ["nxos", "os10"],
        }
    ]
    assert "commands" not in actions[0]


def test_preflight_checks_credentials_and_pinned_host_without_connecting(
    tmp_path: Path, monkeypatch
) -> None:
    inventory = tmp_path / "inventory.yaml"
    inventory.write_text(
        """
version: 1
targets:
  - id: leaf01
    address: 192.0.2.10
    platform: os10
    credential_profile: lab
""",
        encoding="utf-8",
    )
    catalog = tmp_path / "actions.yaml"
    catalog.write_text(
        """
version: 1
actions:
  platform_version:
    description: Show platform version
    commands:
      nxos: show version
      os10: show version
""",
        encoding="utf-8",
    )
    known_hosts = tmp_path / "known_hosts"
    host_keys = HostKeys()
    host_keys.add("192.0.2.10", "ssh-rsa", RSAKey.generate(1024))
    host_keys.save(str(known_hosts))
    monkeypatch.setenv("IIH_LAB_USERNAME", "reader")
    monkeypatch.setenv("IIH_LAB_PASSWORD", "not-logged")
    service = InsightService(
        RuntimePaths(
            inventory=inventory,
            catalog=catalog,
            known_hosts=known_hosts,
            evidence_dir=None,
        )
    )

    checks = service.preflight(("leaf01",))

    assert checks[0].credential_available is True
    assert checks[0].host_key_pinned is True
    assert checks[0].ready is True


def test_cautious_profile_rejects_sensitive_action_before_transport(tmp_path: Path) -> None:
    inventory = tmp_path / "inventory.yaml"
    inventory.write_text(
        """
version: 1
targets:
  - id: leaf01
    address: 192.0.2.10
    platform: os10
    credential_profile: lab
""",
        encoding="utf-8",
    )
    catalog = tmp_path / "actions.yaml"
    catalog.write_text(
        """
version: 1
actions:
  bgp_configuration:
    description: Show BGP configuration
    sensitive: true
    commands:
      nxos: show running-config section "^router bgp"
      os10: show running-configuration bgp
""",
        encoding="utf-8",
    )
    service = InsightService(
        RuntimePaths(
            inventory=inventory,
            catalog=catalog,
            known_hosts=tmp_path / "known_hosts",
            evidence_dir=None,
        )
    )

    try:
        service.run(RunRequest(target_ids=("leaf01",), action_ids=("bgp_configuration",)))
    except PolicyError as exc:
        assert "does not permit sensitive actions" in str(exc)
    else:
        raise AssertionError("sensitive action was not rejected")


def test_lab_profile_requires_lab_target_tag(tmp_path: Path) -> None:
    inventory = tmp_path / "inventory.yaml"
    inventory.write_text(
        """
version: 1
targets:
  - id: leaf01
    address: 192.0.2.10
    platform: os10
    credential_profile: lab
""",
        encoding="utf-8",
    )
    catalog = tmp_path / "actions.yaml"
    catalog.write_text(
        """
version: 1
actions:
  platform_version:
    description: Show platform version
    commands:
      nxos: show version
      os10: show version
""",
        encoding="utf-8",
    )
    service = InsightService(
        RuntimePaths(
            inventory=inventory,
            catalog=catalog,
            known_hosts=tmp_path / "known_hosts",
            evidence_dir=None,
            profile_id="lab",
        )
    )

    try:
        service.run(RunRequest(target_ids=("leaf01",), action_ids=("platform_version",)))
    except PolicyError as exc:
        assert "missing profile-required tags: lab" in str(exc)
    else:
        raise AssertionError("untagged target was not rejected")
