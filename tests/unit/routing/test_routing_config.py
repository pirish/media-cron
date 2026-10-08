from pathlib import Path

from media_cron.config import MediaCronConfig
from media_cron.routing.models import (
    DestinationEndpointConfig,
    DestinationEndpointType,
    MediaRouteConfig,
    SourceEndpointConfig,
    SourceEndpointType,
)


def test_endpoint_config_defaults():
    src = SourceEndpointConfig()
    assert src.type == SourceEndpointType.DIRECTORY
    assert src.path is None
    assert src.client_profile is None
    assert src.category is None
    assert src.min_progress == 1.0

    dest = DestinationEndpointConfig()
    assert dest.type == DestinationEndpointType.LIBRARY
    assert dest.path is None
    assert dest.template is None

    route = MediaRouteConfig()
    assert route.sources == []
    assert route.destination is None
    assert route.transfer_mode is None


def test_yaml_config_parsing_per_media_routing(tmp_path: Path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        """
paths:
  source_dir: "/default/source"
  destination_dir: "/default/dest"

music:
  enabled: true
  transfer_mode: "copy"
  sources:
    - type: "directory"
      path: "/custom/music/inbox"
    - type: "torrent"
      client_profile: "qb_music"
      category: "music"
      tag: "flac"
  destination:
    type: "library"
    path: "/mnt/fast/Music"
    template: "{artist}/{album}/{title}.{ext}"

books:
  enabled: true
  sources:
    - type: "directory"
      path: "/custom/books/inbox"
  destination:
    type: "library"
    path: "/mnt/storage/Books"

audiobook:
  enabled: true
  destination:
    type: "library"
    path: "/mnt/storage/Audiobooks"

video:
  enabled: true
  movies:
    transfer_mode: "hardlink"
    sources:
      - type: "torrent"
        category: "radarr"
    destination:
      type: "library"
      path: "/mnt/storage/Movies"
  tv:
    transfer_mode: "move"
    sources:
      - type: "torrent"
        category: "sonarr"
    destination:
      type: "spool"
      path: "/mnt/storage/spool/tv"
"""
    )

    config = MediaCronConfig.load(cfg_file)

    # Music checks
    assert config.music.route.transfer_mode == "copy"
    assert len(config.music.route.sources) == 2
    assert config.music.route.sources[0].type == SourceEndpointType.DIRECTORY
    assert config.music.route.sources[0].path == Path("/custom/music/inbox")
    assert config.music.route.sources[1].type == SourceEndpointType.TORRENT
    assert config.music.route.sources[1].client_profile == "qb_music"
    assert config.music.route.sources[1].category == "music"
    assert config.music.route.sources[1].tag == "flac"
    assert config.music.route.destination is not None
    assert config.music.route.destination.type == DestinationEndpointType.LIBRARY
    assert config.music.route.destination.path == Path("/mnt/fast/Music")
    assert config.music.route.destination.template == "{artist}/{album}/{title}.{ext}"

    # Books checks
    assert len(config.books.route.sources) == 1
    assert config.books.route.sources[0].path == Path("/custom/books/inbox")
    assert config.books.route.destination.path == Path("/mnt/storage/Books")

    # Audiobook checks
    assert config.audiobook.route.sources == []
    assert config.audiobook.route.destination.path == Path("/mnt/storage/Audiobooks")

    # Video checks
    assert config.video.movies_route.transfer_mode == "hardlink"
    assert len(config.video.movies_route.sources) == 1
    assert config.video.movies_route.sources[0].category == "radarr"
    assert config.video.movies_route.destination.path == Path("/mnt/storage/Movies")
    assert config.video.movies_route.destination.type == DestinationEndpointType.LIBRARY

    assert config.video.tv_route.transfer_mode == "move"
    assert len(config.video.tv_route.sources) == 1
    assert config.video.tv_route.sources[0].category == "sonarr"
    assert config.video.tv_route.destination.path == Path("/mnt/storage/spool/tv")
    assert config.video.tv_route.destination.type == DestinationEndpointType.SPOOL


def test_env_var_overrides_per_media_routing(monkeypatch):
    monkeypatch.setenv("MEDIA_CRON_MUSIC_TRANSFER_MODE", "move")
    monkeypatch.setenv("MEDIA_CRON_MUSIC_SOURCE_DIRS", "/env/music1,/env/music2")
    monkeypatch.setenv("MEDIA_CRON_MUSIC_DESTINATION_PATH", "/env/dest/music")
    monkeypatch.setenv("MEDIA_CRON_MUSIC_DESTINATION_TYPE", "spool")

    monkeypatch.setenv("MEDIA_CRON_MOVIES_TRANSFER_MODE", "copy")
    monkeypatch.setenv("MEDIA_CRON_MOVIES_SOURCE_DIRS", "/env/movies")
    monkeypatch.setenv("MEDIA_CRON_MOVIES_TORRENT_CATEGORY", "env_radarr")
    monkeypatch.setenv("MEDIA_CRON_MOVIES_DESTINATION_PATH", "/env/dest/movies")
    monkeypatch.setenv("MEDIA_CRON_MOVIES_DESTINATION_TYPE", "library")

    monkeypatch.setenv("MEDIA_CRON_TV_SOURCE_DIRS", "/env/tv")
    monkeypatch.setenv("MEDIA_CRON_TV_TORRENT_CATEGORY", "env_sonarr")
    monkeypatch.setenv("MEDIA_CRON_TV_DESTINATION_PATH", "/env/dest/tv")
    monkeypatch.setenv("MEDIA_CRON_TV_DESTINATION_TYPE", "spool")

    config = MediaCronConfig.load(Path("/nonexistent"))

    # Music env overrides
    assert config.music.route.transfer_mode == "move"
    assert len(config.music.route.sources) == 2
    assert config.music.route.sources[0].path == Path("/env/music1")
    assert config.music.route.sources[1].path == Path("/env/music2")
    assert config.music.route.destination.path == Path("/env/dest/music")
    assert config.music.route.destination.type == DestinationEndpointType.SPOOL

    # Movies env overrides
    assert config.video.movies_route.transfer_mode == "copy"
    assert any(s.path == Path("/env/movies") for s in config.video.movies_route.sources)
    assert any(s.category == "env_radarr" for s in config.video.movies_route.sources)
    assert config.video.movies_route.destination.path == Path("/env/dest/movies")
    assert config.video.movies_route.destination.type == DestinationEndpointType.LIBRARY

    # TV env overrides
    assert any(s.path == Path("/env/tv") for s in config.video.tv_route.sources)
    assert any(s.category == "env_sonarr" for s in config.video.tv_route.sources)
    assert config.video.tv_route.destination.path == Path("/env/dest/tv")
    assert config.video.tv_route.destination.type == DestinationEndpointType.SPOOL
