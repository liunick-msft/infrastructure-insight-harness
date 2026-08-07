"""Load operator-owned execution policy profiles."""

from pathlib import Path
from typing import Any

import yaml

from .models import ExecutionPolicy, PolicyDocument


class PolicyError(ValueError):
    """Raised when execution policy is invalid or a profile is unknown."""


def _load_yaml(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as stream:
            return yaml.safe_load(stream)
    except (OSError, yaml.YAMLError) as exc:
        raise PolicyError(f"cannot load execution policy: {exc}") from exc


class PolicyProfiles:
    def __init__(self, document: PolicyDocument) -> None:
        self._document = document

    @classmethod
    def load(cls, path: Path) -> "PolicyProfiles":
        try:
            document = PolicyDocument.model_validate(_load_yaml(path))
        except (TypeError, ValueError) as exc:
            raise PolicyError(f"invalid execution policy: {exc}") from exc
        return cls(document)

    def require(self, profile_id: str) -> ExecutionPolicy:
        try:
            return self._document.profiles[profile_id]
        except KeyError as exc:
            raise PolicyError(f"unknown execution profile: {profile_id}") from exc