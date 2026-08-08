"""Load and expand reviewed diagnostic playbooks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .catalog import ActionCatalog
from .models import Playbook, PlaybookDocument, Platform


class PlaybookError(ValueError):
    """Raised when a playbook is invalid or unavailable."""


def _load_yaml(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as stream:
            return yaml.safe_load(stream)
    except (OSError, yaml.YAMLError) as exc:
        raise PlaybookError(f"cannot load playbook catalog: {exc}") from exc


class PlaybookCatalog:
    def __init__(self, document: PlaybookDocument) -> None:
        self._document = document

    @classmethod
    def load(cls, path: Path) -> PlaybookCatalog:
        try:
            document = PlaybookDocument.model_validate(_load_yaml(path))
        except (TypeError, ValueError) as exc:
            raise PlaybookError(f"invalid playbook catalog: {exc}") from exc
        return cls(document)

    @property
    def version(self) -> int:
        return self._document.version

    def list_playbooks(self) -> dict[str, Playbook]:
        return dict(self._document.playbooks)

    def require(self, playbook_id: str) -> Playbook:
        try:
            return self._document.playbooks[playbook_id]
        except KeyError as exc:
            raise PlaybookError(f"unknown playbook: {playbook_id}") from exc

    def expand(
        self,
        playbook_id: str,
        platform: Platform,
        action_catalog: ActionCatalog,
    ) -> tuple[str, ...]:
        playbook = self.require(playbook_id)
        if platform not in playbook.platforms:
            raise PlaybookError(
                f"playbook {playbook_id!r} does not support platform {platform.value!r}"
            )

        action_ids = tuple(dict.fromkeys(playbook.action_ids))
        for action_id in (*action_ids, *playbook.covered_action_ids):
            action_catalog.require(action_id)
        return action_ids
