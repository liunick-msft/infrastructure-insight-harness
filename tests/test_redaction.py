from datetime import UTC, datetime

from infrastructure_insight.redaction import bound_evidence, redact_output


def test_common_configuration_secrets_are_redacted() -> None:
    output = "username admin password cleartext\nsnmp-server community private ro"

    redacted = redact_output(output)

    assert "cleartext" not in redacted
    assert "private" not in redacted
    assert redacted.count("<redacted>") == 2


def test_oversized_evidence_is_hashed_truncated_and_spilled(tmp_path) -> None:
    evidence = bound_evidence(
        "0123456789",
        max_inline_bytes=5,
        evidence_dir=tmp_path,
        target_id="leaf01",
        action_id="platform_version",
        collected_at=datetime(2026, 8, 7, tzinfo=UTC),
    )

    assert evidence.output == "01234"
    assert evidence.byte_count == 10
    assert evidence.truncated is True
    assert evidence.evidence_path is not None
    assert evidence.evidence_path.read_text(encoding="utf-8") == "0123456789"


def test_evidence_is_persisted_when_inline_output_is_not_truncated(tmp_path) -> None:
    evidence = bound_evidence(
        "username operator password cleartext",
        max_inline_bytes=1024,
        evidence_dir=tmp_path,
        target_id="target01",
        action_id="configuration",
        collected_at=datetime(2026, 8, 7, tzinfo=UTC),
    )

    assert evidence.output == "username operator password <redacted>"
    assert evidence.truncated is False
    assert evidence.evidence_path is not None
    assert evidence.evidence_path.read_text(encoding="utf-8") == evidence.output
