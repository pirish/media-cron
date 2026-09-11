import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from media_cron.config import MediaCronConfig
from media_cron.review.manager import ReviewManager
from media_cron.review.models import (
    ReviewAction,
    ReviewStatus,
    UserAnnotation,
)
from tests.unit.review.test_review_cli import create_sample_review_item


def test_resolve_organize_now_movie(tmp_path: Path):
    review_dir = tmp_path / "review"
    dest_dir = tmp_path / "dest"
    staging_dir = tmp_path / "staging"
    dest_dir.mkdir()
    staging_dir.mkdir()

    cfg = MediaCronConfig()
    cfg.paths.review_dir = review_dir
    cfg.paths.destination_dir = dest_dir
    cfg.paths.staging_dir = staging_dir

    create_sample_review_item(review_dir, "item_mov_1", "solaris.mkv", "movie")
    manager = ReviewManager(review_dir=review_dir)

    annotation = UserAnnotation(
        category="movie",
        title="Solaris",
        year=1972,
    )

    resolved = manager.resolve_item(
        item_id="item_mov_1",
        annotation=annotation,
        action=ReviewAction.ORGANIZE_NOW,
        config=cfg,
    )

    assert resolved.status == ReviewStatus.RESOLVED
    assert resolved.user_annotation == annotation
    assert resolved.resolved_at is not None

    expected_file = dest_dir / "Movies" / "Solaris (1972)" / "Solaris (1972).mkv"
    assert expected_file.exists()
    assert expected_file.read_bytes() == (b"content" * 10)


def test_resolve_organize_now_dry_run(tmp_path: Path):
    review_dir = tmp_path / "review"
    dest_dir = tmp_path / "dest"
    cfg = MediaCronConfig()
    cfg.paths.review_dir = review_dir
    cfg.paths.destination_dir = dest_dir

    create_sample_review_item(review_dir, "item_dry_1", "dry_test.mkv", "movie")
    manager = ReviewManager(review_dir=review_dir)

    annotation = UserAnnotation(category="movie", title="Dry Movie", year=2020)
    resolved = manager.resolve_item(
        item_id="item_dry_1",
        annotation=annotation,
        action=ReviewAction.ORGANIZE_NOW,
        config=cfg,
        dry_run=True,
    )

    assert resolved.status == ReviewStatus.RESOLVED
    # Disk should NOT be modified
    assert not (dest_dir / "Movies" / "Dry Movie (2020)").exists()
    assert (review_dir / "item_dry_1" / "dry_test.mkv").exists()


def test_resolve_reingest_with_hint(tmp_path: Path):
    review_dir = tmp_path / "review"
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()

    cfg = MediaCronConfig()
    cfg.paths.review_dir = review_dir
    cfg.paths.staging_dir = staging_dir

    create_sample_review_item(review_dir, "item_reingest_1", "notes.epub", "book")
    manager = ReviewManager(review_dir=review_dir)

    annotation = UserAnnotation(
        category="book",
        title="Design Patterns",
        creator="Gang of Four",
        year=1994,
    )

    resolved = manager.resolve_item(
        item_id="item_reingest_1",
        annotation=annotation,
        action=ReviewAction.REINGEST,
        config=cfg,
    )

    assert resolved.status == ReviewStatus.REINGESTED
    reingested_file = staging_dir / "notes.epub"
    assert reingested_file.exists()

    hint_file = staging_dir / "notes.epub.media-cron-hint.json"
    assert hint_file.exists()
    hint_data = json.loads(hint_file.read_text(encoding="utf-8"))
    assert hint_data["title"] == "Design Patterns"
    assert hint_data["creator"] == "Gang of Four"
    assert hint_data["year"] == 1994


def test_resolve_discard(tmp_path: Path):
    review_dir = tmp_path / "review"
    cfg = MediaCronConfig()
    cfg.paths.review_dir = review_dir

    create_sample_review_item(review_dir, "item_discard_1", "junk.dat")
    manager = ReviewManager(review_dir=review_dir)

    resolved = manager.resolve_item(
        item_id="item_discard_1",
        annotation=UserAnnotation(category="junk", title="Junk"),
        action=ReviewAction.DISCARD,
        config=cfg,
    )

    assert resolved.status == ReviewStatus.DISCARDED
    assert not (review_dir / "item_discard_1").exists()


def test_resolve_skip(tmp_path: Path):
    review_dir = tmp_path / "review"
    cfg = MediaCronConfig()
    cfg.paths.review_dir = review_dir

    create_sample_review_item(review_dir, "item_skip_1", "mystery.bin")
    manager = ReviewManager(review_dir=review_dir)

    resolved = manager.resolve_item(
        item_id="item_skip_1",
        annotation=UserAnnotation(category="other", title="Mystery"),
        action=ReviewAction.SKIP,
        config=cfg,
    )

    assert resolved.status == ReviewStatus.PENDING
    assert (review_dir / "item_skip_1" / "mystery.bin").exists()


def test_purge_items_older_than(tmp_path: Path):
    review_dir = tmp_path / "review"
    manager = ReviewManager(review_dir=review_dir)

    # Item 1: 10 days old
    m1 = create_sample_review_item(review_dir, "item_old", "old.mkv")
    m1.created_at = datetime.now(UTC) - timedelta(days=10)
    (review_dir / "item_old" / "manifest.json").write_text(m1.to_json(), encoding="utf-8")

    # Item 2: 2 days old
    m2 = create_sample_review_item(review_dir, "item_new", "new.mkv")
    m2.created_at = datetime.now(UTC) - timedelta(days=2)
    (review_dir / "item_new" / "manifest.json").write_text(m2.to_json(), encoding="utf-8")

    # Dry run purge older than 5 days
    purged_dry = manager.purge_items(older_than_days=5, dry_run=True)
    assert purged_dry == ["item_old"]
    assert (review_dir / "item_old").exists()

    # Live purge older than 5 days
    purged = manager.purge_items(older_than_days=5, dry_run=False)
    assert purged == ["item_old"]
    assert not (review_dir / "item_old").exists()
    assert (review_dir / "item_new").exists()
