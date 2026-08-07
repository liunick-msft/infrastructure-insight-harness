"""Load and query the validated target inventory."""

from pathlib import Path
from typing import Any

import yaml

from .models import InventoryDocument, Target


class InventoryError(ValueError):
    """Raised when inventory data is invalid or a target is unknown."""


def _load_yaml(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as stream:
            return yaml.safe_load(stream)
    except (OSError, yaml.YAMLError) as exc:
        raise InventoryError(f"cannot load inventory: {exc}") from exc


class Inventory:
    def __init__(self, document: InventoryDocument) -> None:
        self._document = document
        self._targets = {target.id: target for target in document.targets}

    @classmethod
    def load(cls, path: Path) -> Inventory:
        try:
            document = InventoryDocument.model_validate(_load_yaml(path))
        except (TypeError, ValueError) as exc:
            raise InventoryError(f"invalid inventory: {exc}") from exc
        return cls(document)

    @property
    def version(self) -> int:
        return self._document.version

    def list_targets(self) -> tuple[Target, ...]:
        return self._document.targets

    def require(self, target_id: str) -> Target:
        try:
            return self._targets[target_id]
        except KeyError as exc:
            raise InventoryError(f"unknown target: {target_id}") from exc
