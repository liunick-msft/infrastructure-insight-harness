"""Strict, direct Netmiko transport."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from netmiko import ConnectHandler
from netmiko.exceptions import (
    NetmikoAuthenticationException,
    NetmikoTimeoutException,
    ReadTimeout,
)
from paramiko.ssh_exception import SSHException

from .credentials import Credentials
from .models import Target
from .platforms import netmiko_device_type


class AuthenticationFailure(RuntimeError):
    pass


class ConnectionTimeout(RuntimeError):
    pass


class CommandTimeout(RuntimeError):
    pass


class TransportFailure(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


class Session(Protocol):
    def execute(self, command: str, read_timeout: float) -> str: ...

    def close(self) -> None: ...


class Transport(Protocol):
    def open(self, target: Target, credentials: Credentials) -> Session: ...


class NetmikoSession:
    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def execute(self, command: str, read_timeout: float) -> str:
        try:
            return str(
                self._connection.send_command(
                    command,
                    read_timeout=read_timeout,
                    strip_prompt=True,
                    strip_command=True,
                )
            )
        except ReadTimeout as exc:
            raise CommandTimeout("device command exceeded its read timeout") from exc
        except NetmikoAuthenticationException as exc:
            raise AuthenticationFailure("device rejected authentication") from exc
        except NetmikoTimeoutException as exc:
            raise ConnectionTimeout("SSH session timed out") from exc
        except (EOFError, OSError, SSHException) as exc:
            raise TransportFailure("SSH session disconnected", retryable=True) from exc

    def close(self) -> None:
        try:
            self._connection.disconnect()
        except Exception:
            pass


class NetmikoTransport:
    def __init__(
        self,
        known_hosts: Path,
        *,
        connect_timeout: int = 10,
        read_timeout: float = 30,
        connector: Callable[..., Any] = ConnectHandler,
    ) -> None:
        if not known_hosts.is_file():
            raise ValueError(f"known-hosts file does not exist: {known_hosts}")
        self.known_hosts = known_hosts.resolve()
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self._connector = connector

    def open(self, target: Target, credentials: Credentials) -> NetmikoSession:
        try:
            connection = self._connector(
                device_type=netmiko_device_type(target.platform),
                host=target.address,
                port=target.port,
                username=credentials.username,
                password=credentials.password,
                secret="",
                allow_agent=False,
                use_keys=False,
                ssh_strict=True,
                system_host_keys=True,
                alt_host_keys=True,
                alt_key_file=str(self.known_hosts),
                conn_timeout=self.connect_timeout,
                auth_timeout=self.connect_timeout,
                banner_timeout=self.connect_timeout,
                blocking_timeout=self.connect_timeout,
                timeout=max(self.connect_timeout, int(self.read_timeout)),
                session_timeout=max(self.connect_timeout, int(self.read_timeout)),
                read_timeout_override=self.read_timeout,
                keepalive=15,
                fast_cli=False,
                global_cmd_verify=True,
            )
        except NetmikoAuthenticationException as exc:
            raise AuthenticationFailure("device rejected authentication") from exc
        except NetmikoTimeoutException as exc:
            raise ConnectionTimeout("SSH connection timed out") from exc
        except (OSError, SSHException) as exc:
            raise TransportFailure("SSH connection failed") from exc
        return NetmikoSession(connection)
