import uuid
from datetime import UTC, datetime

from media_cron.cli import render_text_summary
from media_cron.models import BatchSummary
from media_cron.recovery.models import RecoverySummary


def test_recovery_summary_defaults_and_to_dict():
    rec = RecoverySummary(
        items_scanned=5,
        items_resumed=2,
        transfers_bypassed=1,
        items_purged=1,
        bytes_saved=1048576,
        purge_errors=0,
    )
    d = rec.to_dict()
    assert d == {
        "items_scanned": 5,
        "items_resumed": 2,
        "transfers_bypassed": 1,
        "items_purged": 1,
        "bytes_saved": 1048576,
        "purge_errors": 0,
    }


def test_batch_summary_with_recovery_summary_to_dict():
    rec = RecoverySummary(
        items_scanned=4,
        items_resumed=2,
        transfers_bypassed=1,
        items_purged=1,
        bytes_saved=15299971072,
        purge_errors=0,
    )
    now = datetime.now(UTC)
    summary = BatchSummary(
        started_at=now,
        completed_at=now,
        total_scanned=4,
        recovery_summary=rec,
    )
    d = summary.to_dict()
    assert "recovery" in d
    assert d["recovery"]["items_scanned"] == 4
    assert d["recovery"]["items_resumed"] == 2
    assert d["recovery"]["transfers_bypassed"] == 1
    assert d["recovery"]["items_purged"] == 1
    assert d["recovery"]["bytes_saved"] == 15299971072
    assert d["recovery"]["purge_errors"] == 0


def test_render_text_summary_includes_recovery_telemetry():
    rec = RecoverySummary(
        items_scanned=4,
        items_resumed=2,
        transfers_bypassed=1,
        items_purged=1,
        bytes_saved=15299971072,  # ~14.25 GB
        purge_errors=0,
    )
    now = datetime.now(UTC)
    summary = BatchSummary(
        batch_id=uuid.UUID("8bb18440-0a5f-4a73-bb63-05a7810abb16"),
        started_at=now,
        completed_at=now,
        total_scanned=10,
        processed_count=8,
        recovery_summary=rec,
    )
    output = render_text_summary(summary)
    assert "--- Fast Recovery Telemetry ---" in output
    assert "Candidates Inspected: 4" in output
    assert "Staged Resumed:       2 (re-copy avoided)" in output
    assert "Destination Bypassed: 1 (redundant transfer skipped)" in output
    assert "Corrupt Purged:       1 (cleaned and restarted)" in output
    assert "Data Transfer Saved:  14.25 GB" in output


def test_render_text_summary_omits_recovery_when_no_candidates():
    now = datetime.now(UTC)
    summary = BatchSummary(
        started_at=now,
        completed_at=now,
        total_scanned=10,
        recovery_summary=RecoverySummary(),
    )
    output = render_text_summary(summary)
    assert "--- Fast Recovery Telemetry ---" not in output
