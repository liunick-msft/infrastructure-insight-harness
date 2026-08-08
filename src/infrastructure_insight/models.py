"""Validated domain models for inventory, policy, requests, and results."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


IDENTIFIER_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
HOST_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.:-]{0,252}$")
COMMAND_FORBIDDEN_PATTERN = re.compile(r"[\r\n;|<>]")


class Platform(StrEnum):
    NXOS = "nxos"
    OS10 = "os10"


class CollectionState(StrEnum):
    SUCCESS = "success"
    TRANSPORT_ERROR = "transport_error"
    AUTHENTICATION_ERROR = "authentication_error"
    TIMEOUT = "timeout"
    CLI_ERROR = "cli_error"
    POLICY_ERROR = "policy_error"


class ValidationState(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"


class Target(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    address: str
    platform: Platform
    credential_profile: str
    port: int = Field(default=22, ge=1, le=65535)
    tags: frozenset[str] = frozenset()

    @field_validator("id", "credential_profile")
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        if not IDENTIFIER_PATTERN.fullmatch(value):
            raise ValueError("must be a lowercase identifier")
        return value

    @field_validator("address")
    @classmethod
    def validate_address(cls, value: str) -> str:
        if not HOST_PATTERN.fullmatch(value):
            raise ValueError("must be a hostname or IP address without a URI or username")
        return value

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, values: frozenset[str]) -> frozenset[str]:
        if any(not IDENTIFIER_PATTERN.fullmatch(value) for value in values):
            raise ValueError("tags must be lowercase identifiers")
        return values


class Action(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    description: str = Field(min_length=1, max_length=200)
    sensitive: bool = False
    commands: dict[Platform, str]

    @field_validator("commands")
    @classmethod
    def validate_commands(cls, commands: dict[Platform, str]) -> dict[Platform, str]:
        if set(commands) != set(Platform):
            raise ValueError("commands must define exactly nxos and os10")
        for command in commands.values():
            if COMMAND_FORBIDDEN_PATTERN.search(command) or not command.startswith("show "):
                raise ValueError("catalog commands must be single-line show commands")
        return commands


class CatalogDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: int = Field(ge=1)
    actions: dict[str, Action]

    @field_validator("actions")
    @classmethod
    def validate_action_ids(cls, actions: dict[str, Action]) -> dict[str, Action]:
        if not actions:
            raise ValueError("at least one action is required")
        if any(not IDENTIFIER_PATTERN.fullmatch(action_id) for action_id in actions):
            raise ValueError("action IDs must be lowercase identifiers")
        return actions


class Playbook(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    description: str = Field(min_length=1, max_length=200)
    platforms: frozenset[Platform]
    action_ids: tuple[str, ...] = Field(min_length=1)
    covered_action_ids: frozenset[str] = frozenset()

    @field_validator("action_ids", "covered_action_ids")
    @classmethod
    def validate_action_ids(
        cls, values: tuple[str, ...] | frozenset[str]
    ) -> tuple[str, ...] | frozenset[str]:
        if any(not IDENTIFIER_PATTERN.fullmatch(value) for value in values):
            raise ValueError("playbook action IDs must be lowercase identifiers")
        return values

    @model_validator(mode="after")
    def validate_playbook(self) -> Playbook:
        if not self.platforms:
            raise ValueError("at least one playbook platform is required")
        if set(self.action_ids) & self.covered_action_ids:
            raise ValueError("covered actions cannot also be requested")
        return self


class PlaybookDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: int = Field(ge=1)
    playbooks: dict[str, Playbook]

    @field_validator("playbooks")
    @classmethod
    def validate_playbook_ids(cls, playbooks: dict[str, Playbook]) -> dict[str, Playbook]:
        if not playbooks:
            raise ValueError("at least one playbook is required")
        if any(
            not IDENTIFIER_PATTERN.fullmatch(playbook_id) for playbook_id in playbooks
        ):
            raise ValueError("playbook IDs must be lowercase identifiers")
        return playbooks


class InventoryDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: int = Field(ge=1)
    targets: tuple[Target, ...]

    @model_validator(mode="after")
    def validate_unique_targets(self) -> InventoryDocument:
        target_ids = [target.id for target in self.targets]
        if len(target_ids) != len(set(target_ids)):
            raise ValueError("target IDs must be unique")
        return self


class ExecutionPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    max_targets: int = Field(default=1, ge=1, le=100)
    max_actions_per_target: int = Field(default=5, ge=1, le=50)
    required_target_tags: frozenset[str] = frozenset()
    allow_sensitive_actions: bool = False
    persist_evidence: bool = False
    max_inline_bytes: int = Field(default=32_768, ge=1_024, le=1_048_576)
    command_timeout_seconds: float = Field(default=30, ge=1, le=300)
    target_timeout_seconds: float = Field(default=120, ge=1, le=3_600)
    transient_retries: int = Field(default=1, ge=0, le=1)
    login_spacing_seconds: float = Field(default=0.25, ge=0, le=60)

    @field_validator("required_target_tags")
    @classmethod
    def validate_required_tags(cls, values: frozenset[str]) -> frozenset[str]:
        if any(not IDENTIFIER_PATTERN.fullmatch(value) for value in values):
            raise ValueError("required target tags must be lowercase identifiers")
        return values


class PolicyDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: int = Field(ge=1)
    profiles: dict[str, ExecutionPolicy]

    @field_validator("profiles")
    @classmethod
    def validate_profile_ids(
        cls, profiles: dict[str, ExecutionPolicy]
    ) -> dict[str, ExecutionPolicy]:
        if not profiles:
            raise ValueError("at least one execution profile is required")
        if any(not IDENTIFIER_PATTERN.fullmatch(profile_id) for profile_id in profiles):
            raise ValueError("profile IDs must be lowercase identifiers")
        return profiles


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    target_ids: tuple[str, ...] = Field(min_length=1)
    action_ids: tuple[str, ...] = Field(min_length=1)

    @field_validator("target_ids", "action_ids")
    @classmethod
    def validate_requested_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("requested IDs must be unique")
        if any(not IDENTIFIER_PATTERN.fullmatch(value) for value in values):
            raise ValueError("requested IDs must be lowercase identifiers")
        return values


class PreflightTarget(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    target_id: str
    credential_available: bool
    host_key_pinned: bool
    ready: bool


class PlannedCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sequence: int = Field(ge=1)
    target_id: str
    target_address: str
    target_port: int = Field(ge=1, le=65535)
    platform: Platform
    action_id: str
    command: str
    description: str
    sensitive: bool


class ExecutionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    plan_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    playbook_id: str
    playbook_version: int = Field(ge=1)
    catalog_version: int = Field(ge=1)
    profile_id: str
    action_ids: tuple[str, ...]
    covered_action_ids: tuple[str, ...]
    commands: tuple[PlannedCommand, ...]


class ActionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    target_id: str
    action_id: str
    collection_state: CollectionState
    validation_state: ValidationState = ValidationState.UNKNOWN
    collected_at: datetime
    output: str | None = None
    error: str | None = None
    byte_count: int = Field(default=0, ge=0)
    sha256: str | None = None
    raw_byte_count: int = Field(default=0, ge=0)
    raw_sha256: str | None = None
    truncated: bool = False
    evidence_path: Path | None = None
    raw_evidence_path: Path | None = None


class RunResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    started_at: datetime
    completed_at: datetime
    results: tuple[ActionResult, ...]
    evidence_dir: Path | None = None
    manifest_path: Path | None = None
