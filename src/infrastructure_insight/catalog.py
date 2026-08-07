"""Load and resolve the contributed action catalog."""

from pathlib import Path
from typing import Any

import yaml

from .models import Action, CatalogDocument, Platform


class CatalogError(ValueError):
    """Raised when catalog policy is invalid or a requested action is unknown."""


def _load_yaml(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as stream:
            return yaml.safe_load(stream)
    except (OSError, yaml.YAMLError) as exc:
        raise CatalogError(f"cannot load action catalog: {exc}") from exc


class ActionCatalog:
    def __init__(self, document: CatalogDocument) -> None:
        self._document = document

    @classmethod
    def load(cls, path: Path) -> ActionCatalog:
        try:
            document = CatalogDocument.model_validate(_load_yaml(path))
        except (TypeError, ValueError) as exc:
            raise CatalogError(f"invalid action catalog: {exc}") from exc
        return cls(document)

    @property
    def version(self) -> int:
        return self._document.version

    def list_actions(self) -> dict[str, Action]:
        return dict(self._document.actions)

    def require(self, action_id: str) -> Action:
        try:
            return self._document.actions[action_id]
        except KeyError as exc:
            raise CatalogError(f"unknown action: {action_id}") from exc

    def resolve(self, action_id: str, platform: Platform) -> str:
        return self.require(action_id).commands[platform]
