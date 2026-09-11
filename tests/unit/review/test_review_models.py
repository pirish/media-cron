from datetime import UTC, datetime
from pathlib import Path

from media_cron.review.models import (
    ReviewAction,
    ReviewManifest,
    ReviewStatus,
    UnrecognizedFile,
    UserAnnotation,
)


def test_review_enums():
    assert ReviewStatus.PENDING.value == "pending"
    assert ReviewStatus.RESOLVED.value == "resolved"
    assert ReviewStatus.DISCARDED.value == "discarded"
    assert ReviewStatus.REINGESTED.value == "reingested"

    assert ReviewAction.ORGANIZE_NOW.value == "organize"
    assert ReviewAction.REINGEST.value == "reingest"
    assert ReviewAction.DISCARD.value == "discard"
    assert ReviewAction.SKIP.value == "skip"


def test_unrecognized_file():
    uf = UnrecognizedFile(
        relative_path=Path("sub/sample.mkv"),
        size_bytes=1024,
        extension=".mkv",
    )
    assert uf.relative_path == Path("sub/sample.mkv")
    assert uf.size_bytes == 1024
    assert uf.extension == ".mkv"


def test_user_annotation():
    ann = UserAnnotation(
        category="movie",
        title="Dune Part Two",
        creator="Denis Villeneuve",
        year=2024,
        season=None,
        episode=None,
        notes="High quality rip",
    )
    assert ann.category == "movie"
    assert ann.title == "Dune Part Two"
    assert ann.creator == "Denis Villeneuve"
    assert ann.year == 2024


def test_review_manifest_serialization():
    now = datetime.now(UTC)
    manifest = ReviewManifest(
        item_id="dune_2024_abc",
        created_at=now,
        original_path="Dune.2024.obscure.mkv",
        is_directory=False,
        total_size_bytes=1048576,
        files=[
            UnrecognizedFile(
                relative_path=Path("Dune.2024.obscure.mkv"),
                size_bytes=1048576,
                extension=".mkv",
            )
        ],
        detected_category_hint="movie",
        failure_reasons=["No scene title matched", "External lookup failed"],
        status=ReviewStatus.PENDING,
    )

    data = manifest.to_dict()
    assert data["item_id"] == "dune_2024_abc"
    assert data["status"] == "pending"
    assert len(data["files"]) == 1
    assert data["files"][0]["extension"] == ".mkv"
    assert data["detected_category_hint"] == "movie"
    assert "No scene title matched" in data["failure_reasons"]

    json_str = manifest.to_json()
    assert '"item_id": "dune_2024_abc"' in json_str

    restored = ReviewManifest.from_dict(data)
    assert restored.item_id == manifest.item_id
    assert restored.status == ReviewStatus.PENDING
    assert restored.total_size_bytes == 1048576
    assert len(restored.files) == 1
    assert restored.files[0].relative_path == Path("Dune.2024.obscure.mkv")

    restored_json = ReviewManifest.from_json(json_str)
    assert restored_json.item_id == manifest.item_id
    assert restored_json.detected_category_hint == "movie"
