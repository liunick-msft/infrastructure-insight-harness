from pathlib import Path

import pytest
import yaml

from infrastructure_insight.catalog import ActionCatalog, CatalogError
from infrastructure_insight.inventory import Inventory, InventoryError
from infrastructure_insight.models import Platform
from infrastructure_insight.service import DEFAULTS_DIR


def write_yaml(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def test_catalog_resolves_platform_commands(tmp_path: Path) -> None:
    path = write_yaml(
        tmp_path,
        "actions.yaml",
        """
version: 1
actions:
  platform_version:
    description: Show platform version
    commands:
      nxos: show version
      os10: show version
""",
    )

    catalog = ActionCatalog.load(path)

    assert catalog.resolve("platform_version", Platform.NXOS) == "show version"
    assert catalog.resolve("platform_version", Platform.OS10) == "show version"


@pytest.mark.parametrize(
    "command",
    [
        "configure terminal",
        "show version; reload",
        "show version\nreload",
        "show version | redirect bootflash:version.txt",
        "show version > version.txt",
    ],
)
def test_catalog_rejects_non_show_or_multistatement_commands(
    tmp_path: Path, command: str
) -> None:
    document = {
        "version": 1,
        "actions": {
            "bad_action": {
                "description": "Must fail",
                "commands": {"nxos": command, "os10": "show version"},
            }
        },
    }
    path = write_yaml(tmp_path, "actions.yaml", yaml.safe_dump(document))

    with pytest.raises(CatalogError, match="single-line show commands"):
        ActionCatalog.load(path)


def test_catalog_rejects_unknown_action(tmp_path: Path) -> None:
    path = write_yaml(
        tmp_path,
        "actions.yaml",
        """
version: 1
actions:
  platform_version:
    description: Show platform version
    commands:
      nxos: show version
      os10: show version
""",
    )

    with pytest.raises(CatalogError, match="unknown action"):
        ActionCatalog.load(path).require("reload")


def test_inventory_rejects_duplicate_target_ids(tmp_path: Path) -> None:
    path = write_yaml(
        tmp_path,
        "inventory.yaml",
        """
version: 1
targets:
  - id: leaf01
    address: 192.0.2.10
    platform: os10
    credential_profile: lab
  - id: leaf01
    address: 192.0.2.11
    platform: nxos
    credential_profile: lab
""",
    )

    with pytest.raises(InventoryError, match="target IDs must be unique"):
        Inventory.load(path)


def test_contributed_catalog_uses_platform_specific_bgp_commands() -> None:
    catalog = ActionCatalog.load(DEFAULTS_DIR / "actions.yaml")

    assert catalog.resolve("bgp_summary", Platform.NXOS) == (
        "show bgp ipv4 unicast summary"
    )
    assert catalog.resolve("bgp_summary", Platform.OS10) == "show ip bgp summary"
    assert catalog.resolve("bgp_configuration", Platform.NXOS) == (
        'show running-config section "^router bgp"'
    )
    assert catalog.resolve("bgp_configuration", Platform.OS10) == (
        "show running-configuration bgp"
    )
