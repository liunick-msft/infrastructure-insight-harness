"""Redact common secrets and bound returned evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
from pathlib import Path
import re


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


def redact_output(output: str) -> str:
    redacted = output
    for pattern in REDACTION_PATTERNS:
        redacted = pattern.sub(r"\1<redacted>\3", redacted)
    return redacted


def _truncate_utf8(value: str, limit: int) -> str:
    return value.encode("utf-8")[:limit].decode("utf-8", errors="ignore")


def bound_evidence(
    output: str,
    *,
    max_inline_bytes: int,
    evidence_dir: Path | None,
    target_id: str,
    action_id: str,
    collected_at: datetime,
) -> BoundedEvidence:
    redacted = redact_output(output)
    encoded = redacted.encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    truncated = len(encoded) > max_inline_bytes
    evidence_path = None

    if evidence_dir is not None:
        evidence_dir.mkdir(parents=True, exist_ok=True)
        timestamp = collected_at.strftime("%Y%m%dT%H%M%S.%fZ")
        evidence_path = (evidence_dir / f"{timestamp}_{target_id}_{action_id}.txt").resolve()
        evidence_path.write_text(redacted, encoding="utf-8")

    return BoundedEvidence(
        output=_truncate_utf8(redacted, max_inline_bytes) if truncated else redacted,
        byte_count=len(encoded),
        sha256=digest,
        truncated=truncated,
        evidence_path=evidence_path,
    )
