from pathlib import Path

from typer.testing import CliRunner

from media_cron.cli import app

runner = CliRunner()


def test_quickstart_scenario_1_per_media_custom_destination_routing(tmp_path: Path):
    """Scenario 1: Verify that music and movie files are routed to separate target directory roots."""
    downloads_dir = tmp_path / "downloads"
    music_dest = tmp_path / "dest_music"
    movies_dest = tmp_path / "dest_movies"
    fallback_dir = tmp_path / "fallback"
    staging_dir = tmp_path / "staging"

    downloads_dir.mkdir()
    music_dest.mkdir()
    movies_dest.mkdir()
    fallback_dir.mkdir()
    staging_dir.mkdir()

    flac_file = downloads_dir / "Daft Punk - Discovery - 01 - One More Time.flac"
    flac_file.write_bytes(b"fLaC" + b"\x00" * 50)
    mkv_file = downloads_dir / "Inception.2010.1080p.mkv"
    mkv_file.write_bytes(b"\x1a\x45\xdf\xa3" + b"video" * 50)

    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(f"""
paths:
  staging_dir: "{staging_dir}"
  destination_dir: "{fallback_dir}"
general:
  mode: "copy"
music:
  enabled: true
  destination:
    type: "library"
    path: "{music_dest}"
video:
  enabled: true
  movies:
    destination:
      type: "library"
      path: "{movies_dest}"
""")

    # 1. Preview dry-run
    res_dry = runner.invoke(
        app,
        [
            "process",
            "--config",
            str(cfg_file),
            "--source",
            str(downloads_dir),
            "--dry-run",
        ],
    )
    assert res_dry.exit_code == 0

    # 2. Live execution
    res_live = runner.invoke(
        app,
        [
            "process",
            "--config",
            str(cfg_file),
            "--source",
            str(downloads_dir),
        ],
    )
    assert res_live.exit_code == 0

    # 3. Verification
    flac_found = list(music_dest.rglob("*.flac"))
    assert len(flac_found) == 1

    mkv_found = list(movies_dest.rglob("*.mkv"))
    assert len(mkv_found) == 1

    # Fallback directory was never touched
    assert len(list(fallback_dir.rglob("*"))) == 0


def test_quickstart_scenario_2_multi_source_intake_aggregation(tmp_path: Path):
    """Scenario 2: Verify that a media type can concurrently aggregate inputs from multiple directories."""
    incoming_bandcamp = tmp_path / "incoming_bandcamp"
    incoming_cdrips = tmp_path / "incoming_cdrips"
    music_dest = tmp_path / "dest_music"
    staging_dir = tmp_path / "staging"

    incoming_bandcamp.mkdir()
    incoming_cdrips.mkdir()
    music_dest.mkdir()
    staging_dir.mkdir()

    track1 = incoming_bandcamp / "Artist - Album - 01 - Track1.flac"
    track1.write_bytes(b"fLaC" + b"\x00" * 50)
    track2 = incoming_cdrips / "Artist - Album - 02 - Track2.flac"
    track2.write_bytes(b"fLaC" + b"\x00" * 50)

    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(f"""
paths:
  staging_dir: "{staging_dir}"
general:
  mode: "copy"
music:
  enabled: true
  sources:
    - type: "directory"
      path: "{incoming_bandcamp}"
    - type: "directory"
      path: "{incoming_cdrips}"
  destination:
    type: "library"
    path: "{music_dest}"
""")

    result = runner.invoke(app, ["process", "--config", str(cfg_file)])
    assert result.exit_code == 0

    # Both tracks must be organized into dest_music
    organized_flacs = list(music_dest.rglob("*.flac"))
    assert len(organized_flacs) == 2


def test_quickstart_scenario_3_mixed_destination_types_library_vs_spool(tmp_path: Path):
    """Scenario 3: Verify movies into library structure and TV shows into atomic spool folder."""
    downloads_dir = tmp_path / "downloads"
    tv_rel_dir = downloads_dir / "Show.Name.S01E01"
    movies_dest = tmp_path / "dest_movies"
    spool_tv = tmp_path / "spool_tv"
    staging_dir = tmp_path / "staging"

    downloads_dir.mkdir()
    tv_rel_dir.mkdir()
    movies_dest.mkdir()
    spool_tv.mkdir()
    staging_dir.mkdir()

    movie_file = downloads_dir / "Movie.Title.2022.1080p.mkv"
    movie_file.write_bytes(b"\x1a\x45\xdf\xa3" + b"video" * 50)

    tv_file = tv_rel_dir / "Show.Name.S01E01.mkv"
    tv_file.write_bytes(b"\x1a\x45\xdf\xa3" + b"video" * 50)
    sub_file = tv_rel_dir / "Show.Name.S01E01.en.srt"
    sub_file.write_text("1\n00:00:01 --> 00:00:02\nSubtitle")

    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(f"""
paths:
  staging_dir: "{staging_dir}"
general:
  mode: "copy"
video:
  enabled: true
  movies:
    destination:
      type: "library"
      path: "{movies_dest}"
  tv:
    destination:
      type: "spool"
      path: "{spool_tv}"
""")

    result = runner.invoke(
        app,
        [
            "process",
            "--config",
            str(cfg_file),
            "--source",
            str(downloads_dir),
        ],
    )
    assert result.exit_code == 0

    # Movie organized into library
    movies = list(movies_dest.rglob("*.mkv"))
    assert len(movies) == 1

    # TV release deposited inside spool_tv
    spooled_tv_files = list(spool_tv.rglob("*.mkv"))
    assert len(spooled_tv_files) == 1


def test_quickstart_scenario_4_strict_source_isolation_review_quarantine(tmp_path: Path):
    """Scenario 4: Verify non-music files placed into music-dedicated source are quarantined to review."""
    music_inbox = tmp_path / "music_inbox"
    music_dest = tmp_path / "dest_music"
    movies_dest = tmp_path / "dest_movies"
    review_dir = tmp_path / "review"
    staging_dir = tmp_path / "staging"

    music_inbox.mkdir()
    music_dest.mkdir()
    movies_dest.mkdir()
    review_dir.mkdir()
    staging_dir.mkdir()

    valid_track = music_inbox / "Valid.Track.flac"
    valid_track.write_bytes(b"fLaC" + b"\x00" * 50)

    stray_movie = music_inbox / "Stray.Movie.2023.mkv"
    stray_movie.write_bytes(b"\x1a\x45\xdf\xa3" + b"video" * 50)

    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(f"""
paths:
  staging_dir: "{staging_dir}"
  review_dir: "{review_dir}"
general:
  mode: "copy"
music:
  enabled: true
  sources:
    - type: "directory"
      path: "{music_inbox}"
  destination:
    type: "library"
    path: "{music_dest}"
video:
  enabled: true
  movies:
    destination:
      type: "library"
      path: "{movies_dest}"
""")

    result = runner.invoke(app, ["process", "--config", str(cfg_file)])
    assert result.exit_code == 0

    # Valid track is in dest_music
    music_files = list(music_dest.rglob("*.flac"))
    assert len(music_files) == 1

    # Stray movie MUST NOT be in dest_movies
    movie_files = list(movies_dest.rglob("*.mkv"))
    assert len(movie_files) == 0

    # Stray movie MUST be quarantined in review_dir
    review_files = list(review_dir.rglob("*Stray.Movie*"))
    assert len(review_files) >= 1


def test_quickstart_scenario_5_mount_safety_protection(tmp_path: Path):
    """Scenario 5: Verify missing destination root causes clean abort without creating directory structure."""
    downloads_dir = tmp_path / "downloads"
    music_dest = tmp_path / "dest_music"
    unmounted_dest = tmp_path / "unmounted_drive" / "movies"
    staging_dir = tmp_path / "staging"

    downloads_dir.mkdir()
    music_dest.mkdir()
    staging_dir.mkdir()

    track = downloads_dir / "track.flac"
    track.write_bytes(b"fLaC" + b"\x00" * 50)
    movie = downloads_dir / "movie.mkv"
    movie.write_bytes(b"\x1a\x45\xdf\xa3" + b"video" * 50)

    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(f"""
paths:
  staging_dir: "{staging_dir}"
general:
  mode: "copy"
music:
  enabled: true
  destination:
    type: "library"
    path: "{music_dest}"
video:
  enabled: true
  movies:
    destination:
      type: "library"
      path: "{unmounted_dest}"
""")

    # 1. Routes validate command fails with exit code 1
    res_val = runner.invoke(app, ["routes", "validate", "--config", str(cfg_file)])
    assert res_val.exit_code == 1

    # 2. Run process command
    res_proc = runner.invoke(
        app,
        [
            "process",
            "--config",
            str(cfg_file),
            "--source",
            str(downloads_dir),
        ],
    )
    assert res_proc.exit_code == 0

    # 3. Music succeeded
    music_files = list(music_dest.rglob("*.flac"))
    assert len(music_files) == 1

    # 4. Unmounted drive was NOT created by mkdir
    assert not (tmp_path / "unmounted_drive").exists()
