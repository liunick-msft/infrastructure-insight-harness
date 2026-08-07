"""Resolve credentials from environment variables without accepting them in requests."""

from dataclasses import dataclass
import os


class CredentialError(ValueError):
    """Raised when an out-of-band credential profile is incomplete."""


@dataclass(frozen=True)
class Credentials:
    username: str
    password: str


class EnvironmentCredentialProvider:
    """Resolve IIH_<PROFILE>_USERNAME and IIH_<PROFILE>_PASSWORD."""

    def get(self, profile: str) -> Credentials:
        prefix = f"IIH_{profile.upper().replace('-', '_')}"
        username = os.environ.get(f"{prefix}_USERNAME")
        password = os.environ.get(f"{prefix}_PASSWORD")
        if not username or not password:
            raise CredentialError(f"credential profile {profile!r} is incomplete")
        return Credentials(username=username, password=password)
