"""Shared application service for CLI and MCP entry points."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import tempfile

from paramiko.hostkeys import HostKeys, InvalidHostKey

from .catalog import ActionCatalog
from .credentials import CredentialError, EnvironmentCredentialProvider
from .inventory import Inventory
from .models import (
    ExecutionPlan,
    ExecutionPolicy,
    PlannedCommand,
    PreflightTarget,
    RunRequest,
    RunResult,
    Target,
)
from .playbooks import PlaybookCatalog, PlaybookError
from .policy import PolicyError, PolicyProfiles
from .runner import InsightRunner
from .ssh import NetmikoTransport


DEFAULTS_DIR = Path(__file__).parent / "defaults"


class PreflightError(ValueError):
    pass


@dataclass(frozen=True)
class RuntimePaths:
    inventory: Path
    known_hosts: Path
    evidence_dir: Path | None
    catalog: Path = DEFAULTS_DIR / "actions.yaml"
    profiles: Path = DEFAULTS_DIR / "profiles.yaml"
    playbooks: Path = DEFAULTS_DIR / "playbooks.yaml"
    profile_id: str = "cautious"

    @classmethod
    def from_environment(cls) -> RuntimePaths:
        inventory_value = os.environ.get("IIH_INVENTORY")
        if not inventory_value:
            raise ValueError("IIH_INVENTORY must identify an operator-owned inventory file")
        evidence_value = os.environ.get("IIH_EVIDENCE_DIR", "")
        return cls(
            inventory=Path(inventory_value),
            known_hosts=Path(
                os.environ.get("IIH_KNOWN_HOSTS", str(Path.home() / ".ssh" / "known_hosts"))
            ).expanduser(),
            evidence_dir=Path(evidence_value) if evidence_value else None,
            catalog=Path(os.environ.get("IIH_CATALOG", DEFAULTS_DIR / "actions.yaml")),
            profiles=Path(os.environ.get("IIH_PROFILES", DEFAULTS_DIR / "profiles.yaml")),
            playbooks=Path(os.environ.get("IIH_PLAYBOOKS", DEFAULTS_DIR / "playbooks.yaml")),
            profile_id=os.environ.get("IIH_PROFILE", "cautious"),
        )


class InsightService:
    def __init__(self, paths: RuntimePaths) -> None:
        self.paths = paths
        self.inventory = Inventory.load(paths.inventory)
        self.catalog = ActionCatalog.load(paths.catalog)
        self.playbooks = PlaybookCatalog.load(paths.playbooks)
        self.policy = PolicyProfiles.load(paths.profiles).require(paths.profile_id)
        self.credentials = EnvironmentCredentialProvider()

    def list_targets(self) -> list[dict[str, object]]:
        return [
            {
                "id": target.id,
                "address": target.address,
                "port": target.port,
                "platform": target.platform.value,
                "tags": sorted(target.tags),
            }
            for target in self.inventory.list_targets()
        ]

    def list_actions(self) -> list[dict[str, object]]:
        return [
            {
                "id": action_id,
                "description": action.description,
                "sensitive": action.sensitive,
                "platforms": sorted(platform.value for platform in action.commands),
            }
            for action_id, action in self.catalog.list_actions().items()
        ]

    def list_playbooks(self) -> list[dict[str, object]]:
        return [
            {
                "id": playbook_id,
                "description": playbook.description,
                "platforms": sorted(platform.value for platform in playbook.platforms),
                "actions": list(playbook.action_ids),
                "covered_actions": sorted(playbook.covered_action_ids),
            }
            for playbook_id, playbook in self.playbooks.list_playbooks().items()
        ]

    def plan_playbook(self, playbook_id: str, target_ids: tuple[str, ...]) -> ExecutionPlan:
        targets = tuple(self.inventory.require(target_id) for target_id in target_ids)
        if not targets:
            raise PlaybookError("at least one target is required")

        platform = targets[0].platform
        if any(target.platform != platform for target in targets):
            raise PlaybookError("a playbook plan cannot mix target platforms")

        action_ids = self.playbooks.expand(playbook_id, platform, self.catalog)
        request = RunRequest(target_ids=target_ids, action_ids=action_ids)
        self._authorize(request, self.policy)
        playbook = self.playbooks.require(playbook_id)

        commands = tuple(
            PlannedCommand(
                sequence=sequence,
                target_id=target.id,
                target_address=target.address,
                target_port=target.port,
                platform=target.platform,
                action_id=action_id,
                command=self.catalog.resolve(action_id, target.platform),
                description=self.catalog.require(action_id).description,
                sensitive=self.catalog.require(action_id).sensitive,
            )
            for sequence, (target, action_id) in enumerate(
                (
                    (target, action_id)
                    for target in targets
                    for action_id in action_ids
                ),
                start=1,
            )
        )
        digest_input = {
            "playbook_id": playbook_id,
            "playbook_version": self.playbooks.version,
            "catalog_version": self.catalog.version,
            "profile_id": self.paths.profile_id,
            "commands": [command.model_dump(mode="json") for command in commands],
        }
        plan_sha256 = hashlib.sha256(
            json.dumps(digest_input, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return ExecutionPlan(
            plan_sha256=plan_sha256,
            playbook_id=playbook_id,
            playbook_version=self.playbooks.version,
            catalog_version=self.catalog.version,
            profile_id=self.paths.profile_id,
            action_ids=action_ids,
            covered_action_ids=tuple(sorted(playbook.covered_action_ids)),
            commands=commands,
        )

    def run_playbook(self, playbook_id: str, target_ids: tuple[str, ...]) -> RunResult:
        plan = self.plan_playbook(playbook_id, target_ids)
        return self.run(RunRequest(target_ids=target_ids, action_ids=plan.action_ids))

    def preflight(self, target_ids: tuple[str, ...] | None = None) -> tuple[PreflightTarget, ...]:
        targets = (
            tuple(self.inventory.require(target_id) for target_id in target_ids)
            if target_ids
            else self.inventory.list_targets()
        )
        host_keys = self._load_host_keys()
        results = []
        for target in targets:
            credential_available = self._credential_available(target)
            host_key_pinned = bool(host_keys.lookup(self._host_key_name(target)))
            results.append(
                PreflightTarget(
                    target_id=target.id,
                    credential_available=credential_available,
                    host_key_pinned=host_key_pinned,
                    ready=credential_available and host_key_pinned,
                )
            )
        return tuple(results)

    def run(self, request: RunRequest) -> RunResult:
        self._authorize(request, self.policy)
        evidence_dir = self.paths.evidence_dir
        if self.policy.persist_evidence and evidence_dir is None:
            evidence_dir = Path(tempfile.gettempdir()) / "infrastructure-insight"
        transport = NetmikoTransport(self.paths.known_hosts)
        runner = InsightRunner(
            self.inventory,
            self.catalog,
            self.credentials,
            transport,
            evidence_dir=evidence_dir if self.policy.persist_evidence else None,
            max_inline_bytes=self.policy.max_inline_bytes,
            read_timeout=self.policy.command_timeout_seconds,
            target_timeout=self.policy.target_timeout_seconds,
            transient_retries=self.policy.transient_retries,
            login_spacing=self.policy.login_spacing_seconds,
        )
        return runner.run(request)

    def _authorize(self, request: RunRequest, policy: ExecutionPolicy) -> None:
        if len(request.target_ids) > policy.max_targets:
            raise PolicyError(
                f"profile {self.paths.profile_id!r} permits at most {policy.max_targets} targets"
            )
        if len(request.action_ids) > policy.max_actions_per_target:
            raise PolicyError(
                f"profile {self.paths.profile_id!r} permits at most "
                f"{policy.max_actions_per_target} actions per target"
            )

        targets = tuple(self.inventory.require(target_id) for target_id in request.target_ids)
        actions = tuple(self.catalog.require(action_id) for action_id in request.action_ids)
        for target in targets:
            missing_tags = policy.required_target_tags - target.tags
            if missing_tags:
                raise PolicyError(
                    f"target {target.id!r} is missing profile-required tags: "
                    f"{', '.join(sorted(missing_tags))}"
                )
        if not policy.allow_sensitive_actions and any(action.sensitive for action in actions):
            raise PolicyError(
                f"profile {self.paths.profile_id!r} does not permit sensitive actions"
            )

    def _load_host_keys(self) -> HostKeys:
        if not self.paths.known_hosts.is_file():
            raise PreflightError(f"known-hosts file does not exist: {self.paths.known_hosts}")
        host_keys = HostKeys()
        try:
            host_keys.load(str(self.paths.known_hosts))
        except (OSError, InvalidHostKey) as exc:
            raise PreflightError(f"cannot load known-hosts file: {exc}") from exc
        return host_keys

    def _credential_available(self, target: Target) -> bool:
        try:
            self.credentials.get(target.credential_profile)
        except CredentialError:
            return False
        return True

    @staticmethod
    def _host_key_name(target: Target) -> str:
        return target.address if target.port == 22 else f"[{target.address}]:{target.port}"
