"""Redact common secrets and bound returned evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import os
from pathlib import Path
import re
import tempfile


REDACTION_PATTERNS = (
    re.compile(
        r"(?im)^(\s*(?:password|secret|community|authentication-key|key-string)\s+)(\S+)(.*)$"
    ),
    re.compile(r"(?im)^(\s*snmp-server\s+community\s+)(\S+)(.*)$"),
    re.compile(r"(?im)^(\s*username\s+\S+\s+(?:password|secret)\s+)(\S+)(.*)$"),
)


@dataclass(frozen=True)
class BoundedEvidence:
    output: str
    byte_count: int
    sha256: str
    truncated: bool
    evidence_path: Path | None
    raw_byte_count: int
    raw_sha256: str
    raw_evidence_path: Path | None


def redact_output(output: str) -> str:
    redacted = output
    for pattern in REDACTION_PATTERNS:
        redacted = pattern.sub(r"\1<redacted>\3", redacted)
    return redacted


def _truncate_utf8(value: str, limit: int) -> str:
    return value.encode("utf-8")[:limit].decode("utf-8", errors="ignore")


def _atomic_write(path: Path, value: str) -> None:
    descriptor, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary_path, 0o600)
        temporary_path.replace(path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def bound_evidence(
    output: str,
    *,
    max_inline_bytes: int,
    evidence_dir: Path | None,
    target_id: str,
    action_id: str,
    collected_at: datetime,
) -> BoundedEvidence:
    raw_encoded = output.encode("utf-8")
    raw_digest = hashlib.sha256(raw_encoded).hexdigest()
    redacted = redact_output(output)
    encoded = redacted.encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    truncated = len(encoded) > max_inline_bytes
    evidence_path = None
    raw_evidence_path = None

    if evidence_dir is not None:
        evidence_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(evidence_dir, 0o700)
        action_dir = evidence_dir / "targets" / target_id / action_id
        action_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(action_dir, 0o700)
        evidence_path = (action_dir / "redacted.txt").resolve()
        raw_evidence_path = (action_dir / "raw.txt").resolve()
        _atomic_write(raw_evidence_path, output)
        _atomic_write(evidence_path, redacted)

    return BoundedEvidence(
        output=_truncate_utf8(redacted, max_inline_bytes) if truncated else redacted,
        byte_count=len(encoded),
        sha256=digest,
        truncated=truncated,
        evidence_path=evidence_path,
        raw_byte_count=len(raw_encoded),
        raw_sha256=raw_digest,
        raw_evidence_path=raw_evidence_path,
    )
