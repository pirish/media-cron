import json
from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from media_cron.cli import app
from media_cron.review.models import ReviewManifest, ReviewStatus, UnrecognizedFile

runner = CliRunner()


def create_sample_review_item(review_dir: Path, item_id: str, filename: str, hint: str = "movie"):
    item_dir = review_dir / item_id
    item_dir.mkdir(parents=True, exist_ok=True)
    f = item_dir / filename
    f.write_bytes(b"content" * 10)

    manifest = ReviewManifest(
        item_id=item_id,
        created_at=datetime.now(UTC),
        original_path=filename,
        is_directory=False,
        total_size_bytes=len(b"content" * 10),
        files=[
            UnrecognizedFile(
                relative_path=Path(filename), size_bytes=len(b"content" * 10), extension=f.suffix
            )
        ],
        detected_category_hint=hint,
        failure_reasons=["Unknown media lookup"],
        status=ReviewStatus.PENDING,
    )
    (item_dir / "manifest.json").write_text(manifest.to_json(), encoding="utf-8")
    return manifest


def test_review_list_text(tmp_path: Path):
    review_dir = tmp_path / "review"
    create_sample_review_item(review_dir, "test_item_1", "video.mkv", "movie")

    result = runner.invoke(app, ["review", "list", "--review-dir", str(review_dir)])
    assert result.exit_code == 0
    assert "test_item_1" in result.output
    assert "video.mkv" in result.output
    assert "movie" in result.output


def test_review_list_json(tmp_path: Path):
    review_dir = tmp_path / "review"
    create_sample_review_item(review_dir, "item_json_1", "music.flac", "music")

    result = runner.invoke(
        app, ["review", "list", "--review-dir", str(review_dir), "--format", "json"]
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["item_id"] == "item_json_1"
    assert data[0]["detected_category_hint"] == "music"


def test_review_show_text(tmp_path: Path):
    review_dir = tmp_path / "review"
    create_sample_review_item(review_dir, "item_show_1", "book.epub", "book")

    result = runner.invoke(app, ["review", "show", "item_show_1", "--review-dir", str(review_dir)])
    assert result.exit_code == 0
    assert "item_show_1" in result.output
    assert "book.epub" in result.output
    assert "Unknown media lookup" in result.output


def test_review_show_json(tmp_path: Path):
    review_dir = tmp_path / "review"
    create_sample_review_item(review_dir, "item_show_2", "clip.mp4", "movie")

    result = runner.invoke(
        app, ["review", "show", "item_show_2", "--review-dir", str(review_dir), "--format", "json"]
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["item_id"] == "item_show_2"
    assert data["detected_category_hint"] == "movie"


def test_review_show_missing_item(tmp_path: Path):
    review_dir = tmp_path / "review"
    review_dir.mkdir()

    result = runner.invoke(
        app, ["review", "show", "non_existent_id", "--review-dir", str(review_dir)]
    )
    assert result.exit_code != 0
