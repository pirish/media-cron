from pathlib import Path

from media_cron.config import MediaCronConfig, VideoConfig


def test_video_config_defaults():
    cfg = VideoConfig()
    assert cfg.enabled is True
    assert cfg.workflow_mode == "direct"
    assert cfg.spool_dir is None
    assert cfg.post_ingest_command is None
    assert cfg.preserve_companions is True
    assert cfg.library_movies_dir == "Movies"
    assert cfg.library_tv_dir == "TV"
    assert cfg.media_server.enabled is False
    assert cfg.media_server.provider == "jellyfin"
    assert cfg.media_server.timeout_seconds == 5.0
    assert cfg.media_server.max_retries == 0


def test_video_config_yaml_loading(tmp_path):
    yaml_content = """
video:
  enabled: true
  workflow_mode: "spool"
  spool_dir: "/drop/video"
  post_ingest_command: "sh /notify.sh {release_path}"
  preserve_companions: false
  library_movies_dir: "Film"
  library_tv_dir: "Series"
  media_server:
    enabled: true
    provider: "plex"
    url: "http://plex:32400"
    token: "my-plex-token"
    library_id: "5"
    timeout_seconds: 3.5
    max_retries: 2
"""
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(yaml_content)

    cfg = MediaCronConfig.load(cfg_file)
    assert cfg.video.enabled is True
    assert cfg.video.workflow_mode == "spool"
    assert cfg.video.spool_dir == Path("/drop/video")
    assert cfg.video.post_ingest_command == "sh /notify.sh {release_path}"
    assert cfg.video.preserve_companions is False
    assert cfg.video.library_movies_dir == "Film"
    assert cfg.video.library_tv_dir == "Series"
    assert cfg.video.media_server.enabled is True
    assert cfg.video.media_server.provider == "plex"
    assert cfg.video.media_server.url == "http://plex:32400"
    assert cfg.video.media_server.token == "my-plex-token"
    assert cfg.video.media_server.library_id == "5"
    assert cfg.video.media_server.timeout_seconds == 3.5
    assert cfg.video.media_server.max_retries == 2


def test_video_config_dynamic_mode_inference(tmp_path):
    # If spool_dir is set without explicit workflow_mode, defaults to spool
    yaml_content = """
video:
  spool_dir: "/drop/video"
"""
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(yaml_content)

    cfg = MediaCronConfig.load(cfg_file)
    assert cfg.video.workflow_mode == "spool"

    # If workflow_mode is explicitly set to direct, keep direct even if spool_dir is present
    yaml_content_explicit = """
video:
  workflow_mode: "direct"
  spool_dir: "/drop/video"
"""
    cfg_file2 = tmp_path / "config2.yaml"
    cfg_file2.write_text(yaml_content_explicit)

    cfg2 = MediaCronConfig.load(cfg_file2)
    assert cfg2.video.workflow_mode == "direct"


def test_video_config_env_overrides(monkeypatch):
    monkeypatch.setenv("MEDIA_CRON_VIDEO_ENABLED", "false")
    monkeypatch.setenv("MEDIA_CRON_VIDEO_MODE", "hybrid")
    monkeypatch.setenv("MEDIA_CRON_VIDEO_SPOOL_DIR", "/env/spool")
    monkeypatch.setenv("MEDIA_CRON_VIDEO_POST_COMMAND", "echo '{release_path}'")
    monkeypatch.setenv("MEDIA_CRON_VIDEO_PRESERVE_COMPANIONS", "false")
    monkeypatch.setenv("MEDIA_CRON_MEDIA_SERVER_ENABLED", "true")
    monkeypatch.setenv("MEDIA_CRON_MEDIA_SERVER_PROVIDER", "emby")
    monkeypatch.setenv("MEDIA_CRON_MEDIA_SERVER_URL", "http://emby:8096")
    monkeypatch.setenv("MEDIA_CRON_MEDIA_SERVER_TOKEN", "emby_token")
    monkeypatch.setenv("MEDIA_CRON_MEDIA_SERVER_LIBRARY_ID", "lib-99")
    monkeypatch.setenv("MEDIA_CRON_MEDIA_SERVER_MAX_RETRIES", "3")

    cfg = MediaCronConfig.load(Path("/nonexistent"))
    assert cfg.video.enabled is False
    assert cfg.video.workflow_mode == "hybrid"
    assert cfg.video.spool_dir == Path("/env/spool")
    assert cfg.video.post_ingest_command == "echo '{release_path}'"
    assert cfg.video.preserve_companions is False
    assert cfg.video.media_server.enabled is True
    assert cfg.video.media_server.provider == "emby"
    assert cfg.video.media_server.url == "http://emby:8096"
    assert cfg.video.media_server.token == "emby_token"
    assert cfg.video.media_server.library_id == "lib-99"
    assert cfg.video.media_server.max_retries == 3
