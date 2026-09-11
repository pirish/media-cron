from pathlib import Path

from media_cron.config import GeneralConfig, MediaCronConfig, PathsConfig
from media_cron.review.manager import ReviewManager
from media_cron.review.models import ReviewStatus


def test_stage_unrecognized_single_file(tmp_path: Path):
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    review_dir = tmp_path / "review"
    review_dir.mkdir()

    file1 = staging_dir / "unidentified_clip.mkv"
    file1.write_bytes(b"video content" * 100)

    cfg = MediaCronConfig(
        paths=PathsConfig(staging_dir=staging_dir, review_dir=review_dir),
        general=GeneralConfig(mode="move"),
    )

    manager = ReviewManager(review_dir=review_dir)
    manifest = manager.stage_unrecognized(
        source_paths=[file1],
        config=cfg,
        failure_reasons=["Failed scene video identification"],
        dry_run=False,
    )

    assert manifest.status == ReviewStatus.PENDING
    assert manifest.detected_category_hint == "movie"
    assert "Failed scene video identification" in manifest.failure_reasons
    assert not file1.exists()  # Moved out of staging

    item_dir = review_dir / manifest.item_id
    assert item_dir.exists()
    assert (item_dir / "unidentified_clip.mkv").exists()
    assert (item_dir / "manifest.json").exists()


def test_stage_unrecognized_directory(tmp_path: Path):
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    review_dir = tmp_path / "review"
    review_dir.mkdir()

    rel_dir = staging_dir / "Obscure_Release_Folder"
    rel_dir.mkdir()
    (rel_dir / "track.flac").write_bytes(b"audio" * 50)
    (rel_dir / "cover.jpg").write_bytes(b"image" * 20)

    cfg = MediaCronConfig(
        paths=PathsConfig(staging_dir=staging_dir, review_dir=review_dir),
        general=GeneralConfig(mode="move"),
    )

    manager = ReviewManager(review_dir=review_dir)
    manifest = manager.stage_unrecognized(
        source_paths=[rel_dir / "track.flac", rel_dir / "cover.jpg"],
        config=cfg,
        failure_reasons=["No music metadata match"],
        dry_run=False,
    )

    assert manifest.is_directory is True
    assert manifest.detected_category_hint == "music"
    assert manifest.total_size_bytes == (len(b"audio" * 50) + len(b"image" * 20))

    item_dir = review_dir / manifest.item_id
    assert item_dir.exists()
    assert (item_dir / "track.flac").exists()
    assert (item_dir / "cover.jpg").exists()
    assert (item_dir / "manifest.json").exists()


def test_stage_unrecognized_dry_run(tmp_path: Path):
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    review_dir = tmp_path / "review"
    review_dir.mkdir()

    file1 = staging_dir / "doc.pdf"
    file1.write_bytes(b"pdf data" * 10)

    cfg = MediaCronConfig(
        paths=PathsConfig(staging_dir=staging_dir, review_dir=review_dir),
        general=GeneralConfig(mode="move"),
    )

    manager = ReviewManager(review_dir=review_dir)
    manifest = manager.stage_unrecognized(
        source_paths=[file1],
        config=cfg,
        failure_reasons=["Book lookup failed"],
        dry_run=True,
    )

    assert manifest.status == ReviewStatus.PENDING
    assert manifest.detected_category_hint == "book"
    assert file1.exists()  # Unmodified in dry-run
    assert not (review_dir / manifest.item_id).exists()  # Not created on disk


def test_stage_unrecognized_torrent_seeding_safety(tmp_path: Path):
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    review_dir = tmp_path / "review"
    review_dir.mkdir()

    seed_file = staging_dir / "seeding_movie.mkv"
    seed_file.write_bytes(b"movie" * 100)

    cfg = MediaCronConfig(
        paths=PathsConfig(staging_dir=staging_dir, review_dir=review_dir),
        general=GeneralConfig(mode="move"),  # configured mode is move!
    )

    manager = ReviewManager(review_dir=review_dir)
    manifest = manager.stage_unrecognized(
        source_paths=[seed_file],
        config=cfg,
        failure_reasons=["Unrecognized video"],
        seeding_paths={seed_file.resolve()},  # actively seeding!
        dry_run=False,
    )

    # Seed file in staging MUST STILL EXIST (copy or hardlink, not move)
    assert seed_file.exists()
    item_dir = review_dir / manifest.item_id
    assert item_dir.exists()
    assert (item_dir / "seeding_movie.mkv").exists()
