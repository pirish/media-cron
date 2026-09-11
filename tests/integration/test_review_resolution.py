from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from media_cron.cli import app
from media_cron.metadata.models import MediaServerRescanResult
from tests.unit.review.test_review_cli import create_sample_review_item

runner = CliRunner()


def test_cli_resolve_organize_and_rescan(tmp_path: Path):
    review_dir = tmp_path / "review"
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"""
paths:
  review_dir: "{review_dir}"
  destination_dir: "{dest_dir}"
video:
  enabled: true
  media_server:
    enabled: true
    provider: jellyfin
    url: "http://localhost:8096"
    token: "secret"
""",
        encoding="utf-8",
    )

    create_sample_review_item(review_dir, "solaris_rev", "solaris.mkv", "movie")

    mock_client = MagicMock()
    mock_client.trigger_rescan.return_value = MediaServerRescanResult(
        success=True,
        server_type="jellyfin",
        endpoint="http://localhost:8096",
        status_code=200,
        duration_seconds=0.1,
    )

    with patch(
        "media_cron.metadata.media_servers.get_media_server_client", return_value=mock_client
    ):
        res = runner.invoke(
            app,
            [
                "review",
                "resolve",
                "solaris_rev",
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
    assert (dest_dir / "Movies" / "Solaris (1972)" / "Solaris (1972).mkv").exists()
    mock_client.trigger_rescan.assert_called_once()


def test_cli_resolve_reingest(tmp_path: Path):
    review_dir = tmp_path / "review"
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"""
paths:
  review_dir: "{review_dir}"
  staging_dir: "{staging_dir}"
  destination_dir: "{tmp_path / "dest"}"
""",
        encoding="utf-8",
    )

    create_sample_review_item(review_dir, "gof_rev", "notes.epub", "book")

    res = runner.invoke(
        app,
        [
            "review",
            "resolve",
            "gof_rev",
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


def test_cli_discard_force_required(tmp_path: Path):
    review_dir = tmp_path / "review"
    create_sample_review_item(review_dir, "item_del", "trash.txt")

    # Without --force in non-interactive environment, it must fail or prompt
    res = runner.invoke(app, ["review", "discard", "item_del", "--review-dir", str(review_dir)])
    assert res.exit_code != 0
    assert (review_dir / "item_del").exists()

    # With --force, it should succeed
    res_force = runner.invoke(
        app, ["review", "discard", "item_del", "--force", "--review-dir", str(review_dir)]
    )
    assert res_force.exit_code == 0
    assert not (review_dir / "item_del").exists()


def test_cli_purge_force_required(tmp_path: Path):
    review_dir = tmp_path / "review"
    m = create_sample_review_item(review_dir, "item_stale", "stale.mkv")
    m.created_at = datetime.now(UTC) - timedelta(days=20)
    (review_dir / "item_stale" / "manifest.json").write_text(m.to_json(), encoding="utf-8")

    # Without --force
    res = runner.invoke(
        app, ["review", "purge", "--older-than", "10", "--review-dir", str(review_dir)]
    )
    assert res.exit_code != 0
    assert (review_dir / "item_stale").exists()

    # With --force
    res_force = runner.invoke(
        app,
        ["review", "purge", "--older-than", "10", "--force", "--review-dir", str(review_dir)],
    )
    assert res_force.exit_code == 0
    assert not (review_dir / "item_stale").exists()
