import json
from pathlib import Path

from typer.testing import CliRunner

from media_cron.cli import app

runner = CliRunner()


def test_routes_list_human_readable(tmp_path: Path):
    music_dest = tmp_path / "music_lib"
    music_dest.mkdir()

    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(f"""
paths:
  destination_dir: "{tmp_path}/default_dest"
music:
  enabled: true
  route:
    destination:
      type: library
      path: "{music_dest}"
    transfer_mode: copy
""")

    result = runner.invoke(app, ["routes", "list", "--config", str(cfg_file)])
    assert result.exit_code == 0
    assert "Resolved Media Routing Configuration" in result.output
    assert "music" in result.output
    assert "copy" in result.output
    assert str(music_dest) in result.output


def test_routes_list_json(tmp_path: Path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(f"""
paths:
  destination_dir: "{tmp_path}/default_dest"
""")

    result = runner.invoke(app, ["routes", "list", "--config", str(cfg_file), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "music" in data
    assert "movies" in data
    assert "tv" in data
    assert "books" in data
    assert "audiobooks" in data


def test_routes_validate_success(tmp_path: Path):
    music_dest = tmp_path / "music_lib"
    movie_dest = tmp_path / "movie_lib"
    default_dest = tmp_path / "default_dest"

    music_dest.mkdir()
    movie_dest.mkdir()
    default_dest.mkdir()

    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(f"""
paths:
  destination_dir: "{default_dest}"
music:
  enabled: true
  route:
    destination:
      type: library
      path: "{music_dest}"
video:
  enabled: true
  movies_route:
    destination:
      type: library
      path: "{movie_dest}"
""")

    result = runner.invoke(app, ["routes", "validate", "--config", str(cfg_file)])
    assert result.exit_code == 0
    assert "All destination routes valid" in result.output or "Valid" in result.output


def test_routes_validate_failure_on_missing_destination(tmp_path: Path):
    missing_dest = tmp_path / "unmounted_volume" / "movies"

    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(f"""
paths:
  destination_dir: "{tmp_path}/default_dest"
video:
  enabled: true
  movies_route:
    destination:
      type: library
      path: "{missing_dest}"
""")

    result = runner.invoke(app, ["routes", "validate", "--config", str(cfg_file)])
    assert result.exit_code == 1
    assert (
        "missing" in result.output.lower()
        or "unmounted" in result.output.lower()
        or "error" in result.output.lower()
    )


def test_routes_validate_json_output(tmp_path: Path):
    missing_dest = tmp_path / "unmounted_volume" / "movies"

    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(f"""
paths:
  destination_dir: "{tmp_path}/default_dest"
video:
  enabled: true
  movies_route:
    destination:
      type: library
      path: "{missing_dest}"
""")

    result = runner.invoke(app, ["routes", "validate", "--config", str(cfg_file), "--json"])
    assert result.exit_code == 1
    data = json.loads(result.output)
    assert "valid" in data
    assert data["valid"] is False
    assert "routes" in data
