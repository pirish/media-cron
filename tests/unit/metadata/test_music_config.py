from pathlib import Path

from media_cron.config import MediaCronConfig, MusicConfig


def test_music_config_defaults():
    cfg = MusicConfig()
    assert cfg.enabled is True
    assert cfg.workflow_mode == "direct"
    assert cfg.spool_dir is None
    assert cfg.post_ingest_command is None
    assert cfg.enable_external_lookup is False
    assert cfg.provider == "musicbrainz"
    assert cfg.confidence_threshold == 0.85
    assert "musicbrainz" in cfg.providers
    assert cfg.providers["musicbrainz"].enabled is True


def test_music_config_env_overrides(monkeypatch):
    monkeypatch.setenv("MEDIA_CRON_MUSIC_ENABLED", "true")
    monkeypatch.setenv("MEDIA_CRON_MUSIC_MODE", "spool")
    monkeypatch.setenv("MEDIA_CRON_MUSIC_SPOOL_DIR", "/var/spool/beets")
    monkeypatch.setenv("MEDIA_CRON_MUSIC_POST_COMMAND", "beet import -q {release_path}")
    monkeypatch.setenv("MEDIA_CRON_MUSIC_LOOKUP", "true")
    monkeypatch.setenv("MEDIA_CRON_MUSIC_PROVIDER", "discogs")
    monkeypatch.setenv("MEDIA_CRON_DISCOGS_TOKEN", "secret_token_123")
    monkeypatch.setenv("MEDIA_CRON_MUSIC_CONFIDENCE_THRESHOLD", "0.90")

    app_cfg = MediaCronConfig.load()
    assert app_cfg.music.enabled is True
    assert app_cfg.music.workflow_mode == "spool"
    assert app_cfg.music.spool_dir == Path("/var/spool/beets")
    assert app_cfg.music.post_ingest_command == "beet import -q {release_path}"
    assert app_cfg.music.enable_external_lookup is True
    assert app_cfg.music.provider == "discogs"
    assert app_cfg.music.discogs_token == "secret_token_123"
    assert app_cfg.music.confidence_threshold == 0.90


def test_music_spool_dir_dynamic_default(monkeypatch):
    # When spool_dir is set without an explicit mode, default should dynamically switch to spool
    monkeypatch.setenv("MEDIA_CRON_MUSIC_SPOOL_DIR", "/drop/beets")
    app_cfg = MediaCronConfig.load()
    assert app_cfg.music.workflow_mode == "spool"
