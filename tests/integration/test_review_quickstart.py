import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from typer.testing import CliRunner

from media_cron.cli import app
from media_cron.config import MediaCronConfig
from media_cron.pipeline import Pipeline
from media_cron.review.manager import ReviewManager
from media_cron.review.models import ReviewManifest, ReviewStatus, UnrecognizedFile

runner = CliRunner()


def test_quickstart_scenario_1_automated_staging(tmp_path: Path):
    """Scenario 1: Automated Staging of Unrecognized File into Review Directory."""
    staging_dir = tmp_path / "staging"
    dest_dir = tmp_path / "dest"
    review_dir = tmp_path / "review"
    staging_dir.mkdir()
    dest_dir.mkdir()
    review_dir.mkdir()

    # Create unrecognized file in staging (with valid MKV header so integrity check passes)
    unknown_file = staging_dir / "Unknown_obscure_video.mkv"
    unknown_file.write_bytes(b"\x1a\x45\xdf\xa3" + b"sample video bytes" * 20)

    cfg = MediaCronConfig()
    cfg.paths.source_dir = staging_dir
    cfg.paths.staging_dir = staging_dir
    cfg.paths.destination_dir = dest_dir
    cfg.paths.review_dir = review_dir
    cfg.general.mode = "move"
    cfg.plugins.lookups = []  # All lookups fail

    pipeline = Pipeline(config=cfg)
    summary = pipeline.run()

    assert not unknown_file.exists()
    assert summary.unrecognized_count >= 1
    assert summary.review_staged_count >= 1

    manager = ReviewManager(review_dir=review_dir)
    items = manager.list_items()
    assert len(items) == 1
    item = items[0]
    assert "Unknown_obscure_video" in item.item_id
    assert item.status == ReviewStatus.PENDING
    assert item.detected_category_hint == "movie"

    item_folder = review_dir / item.item_id
    assert (item_folder / "Unknown_obscure_video.mkv").exists()
    assert (item_folder / "manifest.json").exists()


def test_quickstart_scenario_2_inspection(tmp_path: Path):
    """Scenario 2: Non-Interactive Inspection (review list & review show)."""
    review_dir = tmp_path / "review"
    review_dir.mkdir()

    # Stage a sample item
    item_dir = review_dir / "sample_item_456"
    item_dir.mkdir()
    (item_dir / "track.flac").write_bytes(b"audio" * 10)
    manifest = ReviewManifest(
        item_id="sample_item_456",
        created_at=datetime.now(UTC),
        original_path="track.flac",
        is_directory=False,
        total_size_bytes=50,
        files=[
            UnrecognizedFile(relative_path=Path("track.flac"), size_bytes=50, extension=".flac")
        ],
        detected_category_hint="music",
        failure_reasons=["Unknown artist/album"],
    )
    (item_dir / "manifest.json").write_text(manifest.to_json(), encoding="utf-8")

    # 1. Text list
    res_list_text = runner.invoke(app, ["review", "list", "--review-dir", str(review_dir)])
    assert res_list_text.exit_code == 0
    assert "sample_item_456" in res_list_text.output
    assert "music" in res_list_text.output

    # 2. JSON list
    res_list_json = runner.invoke(
        app, ["review", "list", "--review-dir", str(review_dir), "--format", "json"]
    )
    assert res_list_json.exit_code == 0
    data = json.loads(res_list_json.output)
    assert len(data) == 1
    item_id = data[0]["item_id"]
    assert item_id == "sample_item_456"

    # 3. Show details
    res_show = runner.invoke(app, ["review", "show", item_id, "--review-dir", str(review_dir)])
    assert res_show.exit_code == 0
    assert "sample_item_456" in res_show.output
    assert "track.flac" in res_show.output
    assert "Unknown artist/album" in res_show.output


def test_quickstart_scenario_3_direct_organization(tmp_path: Path):
    """Scenario 3: Non-Interactive Direct Organization (review resolve --action organize)."""
    review_dir = tmp_path / "review"
    dest_dir = tmp_path / "dest"
    review_dir.mkdir()
    dest_dir.mkdir()

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"""
paths:
  review_dir: "{review_dir}"
  destination_dir: "{dest_dir}"
""",
        encoding="utf-8",
    )

    item_dir = review_dir / "solaris_123"
    item_dir.mkdir()
    (item_dir / "solaris.mkv").write_bytes(b"video data" * 10)
    manifest = ReviewManifest(
        item_id="solaris_123",
        created_at=datetime.now(UTC),
        original_path="solaris.mkv",
        is_directory=False,
        total_size_bytes=100,
        files=[
            UnrecognizedFile(relative_path=Path("solaris.mkv"), size_bytes=100, extension=".mkv")
        ],
        detected_category_hint="movie",
    )
    (item_dir / "manifest.json").write_text(manifest.to_json(), encoding="utf-8")

    res = runner.invoke(
        app,
        [
            "review",
            "resolve",
            "solaris_123",
            "--config",
            str(config_path),
            "--category",
            "movie",
            "--title",
            "Solaris",
            "--year",
            "1972",
            "--action",
            "organize",
        ],
    )

    assert res.exit_code == 0
    organized_target = dest_dir / "Movies" / "Solaris (1972)" / "Solaris (1972).mkv"
    assert organized_target.exists()
    assert not item_dir.exists()


def test_quickstart_scenario_4_reingest(tmp_path: Path):
    """Scenario 4: Non-Interactive Re-Ingest to Staging (review resolve --action reingest)."""
    review_dir = tmp_path / "review"
    staging_dir = tmp_path / "staging"
    dest_dir = tmp_path / "dest"
    review_dir.mkdir()
    staging_dir.mkdir()
    dest_dir.mkdir()

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"""
paths:
  review_dir: "{review_dir}"
  staging_dir: "{staging_dir}"
  destination_dir: "{dest_dir}"
""",
        encoding="utf-8",
    )

    item_dir = review_dir / "custom_notes_123"
    item_dir.mkdir()
    (item_dir / "notes.epub").write_bytes(b"notes content")
    manifest = ReviewManifest(
        item_id="custom_notes_123",
        created_at=datetime.now(UTC),
        original_path="notes.epub",
        is_directory=False,
        total_size_bytes=13,
        files=[
            UnrecognizedFile(relative_path=Path("notes.epub"), size_bytes=13, extension=".epub")
        ],
        detected_category_hint="book",
        failure_reasons=["No author found"],
        status=ReviewStatus.PENDING,
    )
    (item_dir / "manifest.json").write_text(manifest.to_json(), encoding="utf-8")

    res = runner.invoke(
        app,
        [
            "review",
            "resolve",
            "custom_notes_123",
            "--config",
            str(config_path),
            "--category",
            "book",
            "--title",
            "Design Patterns",
            "--creator",
            "Gang of Four",
            "--year",
            "1994",
            "--action",
            "reingest",
        ],
    )

    assert res.exit_code == 0
    assert (staging_dir / "notes.epub").exists()
    hint_file = staging_dir / "notes.epub.media-cron-hint.json"
    assert hint_file.exists()
    hint_data = json.loads(hint_file.read_text(encoding="utf-8"))
    assert hint_data["title"] == "Design Patterns"
    assert hint_data["creator"] == "Gang of Four"
    assert not item_dir.exists()


def test_quickstart_scenario_5_discard_and_purge(tmp_path: Path):
    """Scenario 5: Discard and Retention Purge."""
    review_dir = tmp_path / "review"
    review_dir.mkdir()

    # Create item to discard
    item_discard = review_dir / "item_to_delete"
    item_discard.mkdir()
    (item_discard / "bad.avi").write_bytes(b"corrupted")
    m_discard = ReviewManifest(
        item_id="item_to_delete",
        created_at=datetime.now(UTC),
        original_path="bad.avi",
        is_directory=False,
        total_size_bytes=9,
        files=[UnrecognizedFile(relative_path=Path("bad.avi"), size_bytes=9, extension=".avi")],
    )
    (item_discard / "manifest.json").write_text(m_discard.to_json(), encoding="utf-8")

    # Create expired item for purge (10 days old)
    item_stale = review_dir / "item_stale_10d"
    item_stale.mkdir()
    (item_stale / "stale.dat").write_bytes(b"stale")
    m_stale = ReviewManifest(
        item_id="item_stale_10d",
        created_at=datetime.now(UTC) - timedelta(days=10),
        original_path="stale.dat",
        is_directory=False,
        total_size_bytes=5,
        files=[UnrecognizedFile(relative_path=Path("stale.dat"), size_bytes=5, extension=".dat")],
    )
    (item_stale / "manifest.json").write_text(m_stale.to_json(), encoding="utf-8")

    # 1. Discard
    res_discard = runner.invoke(
        app, ["review", "discard", "item_to_delete", "--force", "--review-dir", str(review_dir)]
    )
    assert res_discard.exit_code == 0
    assert not item_discard.exists()

    # 2. Purge items older than 7 days
    res_purge = runner.invoke(
        app, ["review", "purge", "--older-than", "7", "--force", "--review-dir", str(review_dir)]
    )
    assert res_purge.exit_code == 0
    assert not item_stale.exists()
    assert "Purged 1 item(s)" in res_purge.output
