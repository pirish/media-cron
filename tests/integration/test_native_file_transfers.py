import json
from pathlib import Path

from typer.testing import CliRunner

from media_cron.cli import app
from media_cron.config import MediaCronConfig
from media_cron.pipeline import Pipeline
from media_cron.routing.models import (
    DestinationEndpointConfig,
    DestinationEndpointType,
    MediaRouteConfig,
)
from media_cron.transfer.models import TransferConfig, TransferStrategy


def _create_dummy_mkv(path: Path, size_bytes: int = 2048) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Valid EBML/Matroska magic header + padding
    header = b"\x1a\x45\xdf\xa3"
    path.write_bytes(header + b"\x00" * max(0, size_bytes - len(header)))
    return path


def test_pipeline_native_copy_and_move_transfers(tmp_path: Path) -> None:
    source_dir = tmp_path / "downloads"
    staging_dir = tmp_path / "staging"
    dest_dir = tmp_path / "library"
    dest_dir.mkdir(parents=True, exist_ok=True)

    _create_dummy_mkv(source_dir / "Inception.2010.1080p.mkv", 4096)

    cfg = MediaCronConfig()
    cfg.paths.source_dir = source_dir
    cfg.paths.staging_dir = staging_dir
    cfg.paths.destination_dir = dest_dir
    cfg.general.mode = "move"
    cfg.transfer = TransferConfig(strategy=TransferStrategy.NATIVE)

    pipeline = Pipeline(cfg)
    summary = pipeline.run(dry_run=False)

    assert summary.exit_code == 0
    assert summary.processed_count == 1
    assert summary.transfer_summary is not None
    # 1 move into staging + 1 move into library
    assert summary.transfer_summary.native_count >= 2
    assert summary.transfer_summary.fallback_count == 0
    assert summary.transfer_summary.total_bytes_transferred >= 4096

    organized_files = list(dest_dir.rglob("*.mkv"))
    assert len(organized_files) == 1


def test_pipeline_custom_command_with_special_chars_and_route_override(tmp_path: Path) -> None:
    source_dir = tmp_path / "downloads"
    staging_dir = tmp_path / "staging"
    dest_dir = tmp_path / "library"
    movies_nas = tmp_path / "nas_movies"
    movies_nas.mkdir(parents=True, exist_ok=True)

    # Filename with spaces, brackets, parentheses, and ampersand
    _create_dummy_mkv(
        source_dir / "The Matrix (1999) [1080p] & Extras!.mkv",
        4096,
    )

    cfg = MediaCronConfig()
    cfg.paths.source_dir = source_dir
    cfg.paths.staging_dir = staging_dir
    cfg.paths.destination_dir = dest_dir
    cfg.general.mode = "copy"
    cfg.transfer = TransferConfig(strategy=TransferStrategy.NATIVE)

    # Override movie route destination to use custom copy command
    cfg.video.movies_route = MediaRouteConfig(
        transfer_mode="copy",
        destination=DestinationEndpointConfig(
            type=DestinationEndpointType.LIBRARY,
            path=movies_nas,
            transfer=TransferConfig(
                strategy=TransferStrategy.CUSTOM,
                copy_command="cp -r {src} {dst}",
            ),
        ),
    )

    pipeline = Pipeline(cfg)
    summary = pipeline.run(dry_run=False)

    assert summary.exit_code == 0
    assert summary.processed_count == 1
    assert summary.transfer_summary is not None
    # Staging used global native (mv), movie organization used route custom (cp -r)
    assert summary.transfer_summary.native_count >= 1
    assert summary.transfer_summary.custom_count >= 1

    nas_files = list(movies_nas.rglob("*.mkv"))
    assert len(nas_files) == 1


def test_pipeline_fallback_to_builtin_on_missing_custom_command(tmp_path: Path) -> None:
    source_dir = tmp_path / "downloads"
    staging_dir = tmp_path / "staging"
    dest_dir = tmp_path / "library"
    dest_dir.mkdir(parents=True, exist_ok=True)

    _create_dummy_mkv(source_dir / "Interstellar.2014.1080p.mkv", 4096)

    cfg = MediaCronConfig()
    cfg.paths.source_dir = source_dir
    cfg.paths.staging_dir = staging_dir
    cfg.paths.destination_dir = dest_dir
    cfg.general.mode = "copy"
    cfg.transfer = TransferConfig(
        strategy=TransferStrategy.CUSTOM,
        copy_command="nonexistent_transfer_cli_tool {src} {dst}",
        move_command="nonexistent_transfer_cli_tool {src} {dst}",
        fallback_enabled=True,
    )

    pipeline = Pipeline(cfg)
    summary = pipeline.run(dry_run=False)

    assert summary.exit_code == 0
    assert summary.processed_count == 1
    assert summary.transfer_summary is not None
    assert summary.transfer_summary.builtin_count >= 2
    assert summary.transfer_summary.fallback_count >= 2

    organized_files = list(dest_dir.rglob("*.mkv"))
    assert len(organized_files) == 1


def test_cli_transfer_flags_and_summary_output(tmp_path: Path) -> None:
    source_dir = tmp_path / "downloads"
    staging_dir = tmp_path / "staging"
    dest_dir = tmp_path / "library"
    dest_dir.mkdir(parents=True, exist_ok=True)

    _create_dummy_mkv(source_dir / "Blade.Runner.1982.1080p.mkv", 4096)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "run",
            "--source",
            str(source_dir),
            "--staging",
            str(staging_dir),
            "--dest",
            str(dest_dir),
            "--mode",
            "copy",
            "--transfer-strategy",
            "custom",
            "--copy-cmd",
            "cp -r {src} {dst}",
            "--json",
        ],
    )
    assert result.exit_code == 0
    json_start = result.stdout.find("{\n")
    assert json_start != -1
    payload = json.loads(result.stdout[json_start:])
    assert "transfer_summary" in payload
    assert payload["transfer_summary"]["custom_count"] >= 1


def test_spoolers_converter_seed_and_review_use_transfer_executor(tmp_path: Path) -> None:
    from unittest.mock import patch

    from media_cron.cli import render_text_summary
    from media_cron.metadata.converter import RetentionPolicy, apply_retention_policy
    from media_cron.metadata.music_spooler import MusicSpoolEngine
    from media_cron.models import OperationPlan, OperationType, TransferMode
    from media_cron.plugins.output.seed import SeedRelocatorOutput
    from media_cron.review.manager import ReviewManager
    from media_cron.transfer.executor import FileTransferExecutor

    executor = FileTransferExecutor(TransferConfig(strategy=TransferStrategy.NATIVE))

    # 1. SeedRelocatorOutput EXDEV fallback uses transfer_executor
    src_seed = tmp_path / "seed_src.mkv"
    src_seed.write_bytes(b"seed_payload")
    dst_seed = tmp_path / "seed_dir" / "seed_src.mkv"
    seed_out = SeedRelocatorOutput(transfer_executor=executor)
    plan = OperationPlan(
        op_type=OperationType.SEED_RELOCATE,
        transfer_mode=TransferMode.HARDLINK,
        source_path=src_seed,
        destination_path=dst_seed,
        reason="Test seed",
        dry_run=False,
    )
    with patch("os.link", side_effect=OSError(18, "Invalid cross-device link")):
        res = seed_out.execute(plan)
    assert res.status.value == "SUCCESS"
    assert dst_seed.read_bytes() == b"seed_payload"

    # 2. MusicSpoolEngine cross-device fallback uses transfer_executor
    spooler = MusicSpoolEngine(transfer_executor=executor)
    src_track = tmp_path / "track.flac"
    src_track.write_bytes(b"flac_audio")
    dst_track = tmp_path / "spool" / "track.flac"
    dst_track.parent.mkdir(parents=True, exist_ok=True)
    with patch("os.link", side_effect=OSError(18, "Invalid cross-device link")):
        mode_used = spooler._transfer_file(src_track, dst_track)
    assert mode_used == "copy"
    assert dst_track.read_bytes() == b"flac_audio"

    # 3. Converter apply_retention_policy ARCHIVE uses transfer_executor
    book_src = tmp_path / "book.mobi"
    book_src.write_bytes(b"mobi_data")
    book_epub = tmp_path / "book.epub"
    book_epub.write_bytes(b"epub_data")
    archive_dir = tmp_path / "archive"
    apply_retention_policy(
        source_path=book_src,
        target_path=book_epub,
        retention_policy=RetentionPolicy.ARCHIVE,
        archive_dir=archive_dir,
        transfer_executor=executor,
    )
    assert (archive_dir / "book.mobi").exists()
    assert not book_src.exists()

    # 4. ReviewManager uses transfer_executor
    unrec_file = tmp_path / "mystery.bin"
    unrec_file.write_bytes(b"mystery_bytes")
    review_dir = tmp_path / "review"
    cfg = MediaCronConfig()
    cfg.paths.staging_dir = tmp_path
    cfg.paths.review_dir = review_dir
    cfg.general.mode = "copy"
    review_mgr = ReviewManager(review_dir, transfer_executor=executor)
    manifest = review_mgr.stage_unrecognized([unrec_file], config=cfg)
    assert (review_dir / manifest.item_id / "mystery.bin").exists()

    # Verify executor recorded all 4 native transfers
    summary = executor.get_summary()
    assert summary.native_count == 4

    # 5. Verify render_text_summary includes File Transfer Telemetry
    from datetime import UTC, datetime

    from media_cron.models import BatchSummary

    batch = BatchSummary(
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        transfer_summary=summary,
    )
    rendered = render_text_summary(batch)
    assert "--- File Transfer Telemetry ---" in rendered
    assert "Native Transfers:     4" in rendered
