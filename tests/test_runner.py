from pathlib import Path
import json

import pytest
from pydantic import ValidationError

from infrastructure_insight.catalog import ActionCatalog, CatalogError
from infrastructure_insight.credentials import Credentials
from infrastructure_insight.inventory import Inventory
from infrastructure_insight.models import (
    Action,
    CatalogDocument,
    CollectionState,
    InventoryDocument,
    Platform,
    RunRequest,
    Target,
)
from infrastructure_insight.runner import InsightRunner
from infrastructure_insight.ssh import (
    CommandTimeout,
    NetmikoTransport,
    TransportFailure,
)


class StaticCredentials:
    def get(self, profile: str) -> Credentials:
        return Credentials(username="reader", password="not-logged")


class FakeSession:
    def __init__(self, outputs: dict[str, str]) -> None:
        self.outputs = outputs
        self.closed = False

    def execute(self, command: str, read_timeout: float) -> str:
        return self.outputs[command]

    def close(self) -> None:
        self.closed = True


class FakeTransport:
    def __init__(self) -> None:
        self.opened: list[str] = []

    def open(self, target: Target, credentials: Credentials) -> FakeSession:
        self.opened.append(target.id)
        if target.id == "broken-leaf":
            raise TransportFailure("SSH connection failed")
        return FakeSession({"show version": f"version from {target.platform}"})


def make_runner(transport: FakeTransport) -> InsightRunner:
    inventory = Inventory(
        InventoryDocument(
            version=1,
            targets=(
                Target(
                    id="os10-leaf",
                    address="192.0.2.10",
                    platform=Platform.OS10,
                    credential_profile="lab",
                ),
                Target(
                    id="broken-leaf",
                    address="192.0.2.11",
                    platform=Platform.NXOS,
                    credential_profile="lab",
                ),
            ),
        )
    )
    catalog = ActionCatalog(
        CatalogDocument(
            version=1,
            actions={
                "platform_version": Action(
                    description="Show platform version",
                    commands={
                        Platform.NXOS: "show version",
                        Platform.OS10: "show version",
                    },
                )
            },
        )
    )
    return InsightRunner(
        inventory,
        catalog,
        StaticCredentials(),
        transport,
        login_spacing=0,
    )


def test_unknown_action_is_denied_before_transport_open() -> None:
    transport = FakeTransport()
    runner = make_runner(transport)

    with pytest.raises(CatalogError, match="unknown action"):
        runner.run(RunRequest(target_ids=("os10-leaf",), action_ids=("reload",)))

    assert transport.opened == []


def test_injected_action_id_is_rejected_by_request_schema() -> None:
    with pytest.raises(ValidationError, match="lowercase identifiers"):
        RunRequest(
            target_ids=("os10-leaf",),
            action_ids=("platform_version; reload",),
        )


def test_target_failure_preserves_successful_results() -> None:
    runner = make_runner(FakeTransport())

    result = runner.run(
        RunRequest(
            target_ids=("os10-leaf", "broken-leaf"),
            action_ids=("platform_version",),
        )
    )

    assert [item.collection_state for item in result.results] == [
        CollectionState.SUCCESS,
        CollectionState.TRANSPORT_ERROR,
    ]
    assert result.results[0].output == "version from os10"


def test_netmiko_transport_enforces_strict_host_keys(tmp_path: Path) -> None:
    known_hosts = tmp_path / "known_hosts"
    known_hosts.write_text("example host key", encoding="utf-8")
    captured: dict[str, object] = {}

    class Connection:
        def disconnect(self) -> None:
            pass

    def connector(**kwargs: object) -> Connection:
        captured.update(kwargs)
        return Connection()

    transport = NetmikoTransport(known_hosts, connector=connector)
    target = Target(
        id="os10-leaf",
        address="192.0.2.10",
        platform=Platform.OS10,
        credential_profile="lab",
    )

    transport.open(target, Credentials(username="reader", password="secret"))

    assert captured["device_type"] == "dell_os10"
    assert captured["ssh_strict"] is True
    assert captured["system_host_keys"] is True
    assert captured["alt_host_keys"] is True
    assert captured["alt_key_file"] == str(known_hosts.resolve())
    assert captured["allow_agent"] is False
    assert captured["use_keys"] is False
    assert captured["secret"] == ""


def test_command_timeout_is_classified_without_losing_target_result() -> None:
    class TimeoutSession(FakeSession):
        def execute(self, command: str, read_timeout: float) -> str:
            raise CommandTimeout("device command exceeded its read timeout")

    class TimeoutTransport(FakeTransport):
        def open(self, target: Target, credentials: Credentials) -> TimeoutSession:
            self.opened.append(target.id)
            return TimeoutSession({})

    result = make_runner(TimeoutTransport()).run(
        RunRequest(target_ids=("os10-leaf",), action_ids=("platform_version",))
    )

    assert result.results[0].collection_state == CollectionState.TIMEOUT


def test_transient_disconnect_retries_current_action_once() -> None:
    class DisconnectSession(FakeSession):
        def execute(self, command: str, read_timeout: float) -> str:
            raise TransportFailure("SSH session disconnected", retryable=True)

    class RetryTransport(FakeTransport):
        def open(self, target: Target, credentials: Credentials) -> FakeSession:
            self.opened.append(target.id)
            if len(self.opened) == 1:
                return DisconnectSession({})
            return FakeSession({"show version": "recovered"})

    transport = RetryTransport()
    result = make_runner(transport).run(
        RunRequest(target_ids=("os10-leaf",), action_ids=("platform_version",))
    )

    assert transport.opened == ["os10-leaf", "os10-leaf"]
    assert result.results[0].collection_state == CollectionState.SUCCESS
    assert result.results[0].output == "recovered"


def test_run_persists_raw_redacted_evidence_and_command_manifest(tmp_path: Path) -> None:
    runner = make_runner(FakeTransport())
    runner.evidence_dir = tmp_path

    result = runner.run(
        RunRequest(target_ids=("os10-leaf",), action_ids=("platform_version",))
    )

    action_result = result.results[0]
    assert result.evidence_dir is not None
    assert result.manifest_path is not None
    assert action_result.raw_evidence_path is not None
    assert action_result.raw_evidence_path.read_text(encoding="utf-8") == "version from os10"
    assert action_result.evidence_path is not None
    assert action_result.evidence_path.read_text(encoding="utf-8") == "version from os10"
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["commands"][0]["command"] == "show version"
    assert manifest["commands"][0]["raw_sha256"] == action_result.raw_sha256
