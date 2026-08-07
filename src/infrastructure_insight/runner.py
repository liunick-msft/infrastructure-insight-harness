"""Sequential catalog-authorized validation runner."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
import re
import time
from typing import Protocol

from .catalog import ActionCatalog
from .credentials import CredentialError, Credentials
from .inventory import Inventory
from .models import (
    ActionResult,
    CollectionState,
    RunRequest,
    RunResult,
    Target,
    ValidationState,
)
from .redaction import bound_evidence
from .ssh import (
    AuthenticationFailure,
    CommandTimeout,
    ConnectionTimeout,
    Session,
    Transport,
    TransportFailure,
)


CLI_ERROR_PATTERN = re.compile(
    r"(?im)(?:^%\s*(?:invalid|error|incomplete|ambiguous)|invalid input|unknown command)"
)


class CredentialProvider(Protocol):
    def get(self, profile: str) -> Credentials: ...


class InsightRunner:
    def __init__(
        self,
        inventory: Inventory,
        catalog: ActionCatalog,
        credentials: CredentialProvider,
        transport: Transport,
        *,
        evidence_dir: Path | None = None,
        max_inline_bytes: int = 32_768,
        read_timeout: float = 30,
        target_timeout: float = 120,
        transient_retries: int = 1,
        login_spacing: float = 0.25,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.inventory = inventory
        self.catalog = catalog
        self.credentials = credentials
        self.transport = transport
        self.evidence_dir = evidence_dir
        self.max_inline_bytes = max_inline_bytes
        self.read_timeout = read_timeout
        self.target_timeout = target_timeout
        self.transient_retries = transient_retries
        self.login_spacing = login_spacing
        self._clock = clock
        self._sleeper = sleeper
        self._last_login_attempt: float | None = None

    def run(self, request: RunRequest) -> RunResult:
        started_at = datetime.now(UTC)
        targets = tuple(self.inventory.require(target_id) for target_id in request.target_ids)
        actions = tuple(
            (action_id, self.catalog.require(action_id)) for action_id in request.action_ids
        )
        results: list[ActionResult] = []

        for target in targets:
            target_started = self._clock()
            try:
                credential = self.credentials.get(target.credential_profile)
            except CredentialError as exc:
                results.extend(
                    self._error_results(
                        target.id,
                        request.action_ids,
                        CollectionState.AUTHENTICATION_ERROR,
                        str(exc),
                    )
                )
                continue

            try:
                session = self._open_with_spacing(target, credential)
            except AuthenticationFailure as exc:
                results.extend(
                    self._error_results(
                        target.id,
                        request.action_ids,
                        CollectionState.AUTHENTICATION_ERROR,
                        str(exc),
                    )
                )
                continue
            except ConnectionTimeout as exc:
                results.extend(
                    self._error_results(
                        target.id,
                        request.action_ids,
                        CollectionState.TIMEOUT,
                        str(exc),
                    )
                )
                continue
            except TransportFailure as exc:
                results.extend(
                    self._error_results(
                        target.id,
                        request.action_ids,
                        CollectionState.TRANSPORT_ERROR,
                        str(exc),
                    )
                )
                continue

            try:
                for index, (action_id, action) in enumerate(actions):
                    remaining = self.target_timeout - (self._clock() - target_started)
                    if remaining <= 0:
                        results.extend(
                            self._error_results(
                                target.id,
                                request.action_ids[index:],
                                CollectionState.TIMEOUT,
                                "target operation exceeded its total timeout",
                            )
                        )
                        break

                    command = action.commands[target.platform]
                    try:
                        output = session.execute(command, min(self.read_timeout, remaining))
                    except TransportFailure as exc:
                        if not exc.retryable or self.transient_retries == 0:
                            results.extend(
                                self._error_results(
                                    target.id,
                                    request.action_ids[index:],
                                    CollectionState.TRANSPORT_ERROR,
                                    str(exc),
                                )
                            )
                            break
                        session.close()
                        try:
                            session = self._open_with_spacing(target, credential)
                            output = session.execute(command, min(self.read_timeout, remaining))
                        except (AuthenticationFailure, ConnectionTimeout, TransportFailure) as retry_exc:
                            state = self._state_for_exception(retry_exc)
                            results.extend(
                                self._error_results(
                                    target.id,
                                    request.action_ids[index:],
                                    state,
                                    str(retry_exc),
                                )
                            )
                            break
                        except CommandTimeout as retry_exc:
                            results.append(
                                self._error_result(
                                    target.id,
                                    action_id,
                                    CollectionState.TIMEOUT,
                                    str(retry_exc),
                                )
                            )
                            continue
                    except CommandTimeout as exc:
                        results.append(
                            self._error_result(
                                target.id, action_id, CollectionState.TIMEOUT, str(exc)
                            )
                        )
                        continue
                    except AuthenticationFailure as exc:
                        results.extend(
                            self._error_results(
                                target.id,
                                request.action_ids[index:],
                                CollectionState.AUTHENTICATION_ERROR,
                                str(exc),
                            )
                        )
                        break

                    results.append(self._success_result(target.id, action_id, output))
            finally:
                session.close()

        return RunResult(
            started_at=started_at,
            completed_at=datetime.now(UTC),
            results=tuple(results),
        )

    def _open_with_spacing(self, target: Target, credential: Credentials) -> Session:
        now = self._clock()
        if self._last_login_attempt is not None:
            wait = self.login_spacing - (now - self._last_login_attempt)
            if wait > 0:
                self._sleeper(wait)
        self._last_login_attempt = self._clock()
        return self.transport.open(target, credential)

    def _success_result(self, target_id: str, action_id: str, output: str) -> ActionResult:
        collected_at = datetime.now(UTC)
        evidence = bound_evidence(
            output,
            max_inline_bytes=self.max_inline_bytes,
            evidence_dir=self.evidence_dir,
            target_id=target_id,
            action_id=action_id,
            collected_at=collected_at,
        )
        state = CollectionState.CLI_ERROR if CLI_ERROR_PATTERN.search(output) else CollectionState.SUCCESS
        return ActionResult(
            target_id=target_id,
            action_id=action_id,
            collection_state=state,
            validation_state=ValidationState.UNKNOWN,
            collected_at=collected_at,
            output=evidence.output,
            byte_count=evidence.byte_count,
            sha256=evidence.sha256,
            truncated=evidence.truncated,
            evidence_path=evidence.evidence_path,
        )

    @staticmethod
    def _state_for_exception(exc: Exception) -> CollectionState:
        if isinstance(exc, AuthenticationFailure):
            return CollectionState.AUTHENTICATION_ERROR
        if isinstance(exc, ConnectionTimeout):
            return CollectionState.TIMEOUT
        return CollectionState.TRANSPORT_ERROR

    @staticmethod
    def _error_result(
        target_id: str,
        action_id: str,
        state: CollectionState,
        error: str,
    ) -> ActionResult:
        return ActionResult(
            target_id=target_id,
            action_id=action_id,
            collection_state=state,
            collected_at=datetime.now(UTC),
            error=error,
        )

    def _error_results(
        self,
        target_id: str,
        action_ids: tuple[str, ...],
        state: CollectionState,
        error: str,
    ) -> list[ActionResult]:
        return [self._error_result(target_id, action_id, state, error) for action_id in action_ids]
