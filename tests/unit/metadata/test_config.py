from pathlib import Path

import pytest

from media_cron.config import (
    AudiobookConfig,
    MediaCronConfig,
)


def test_audiobook_config_defaults():
    cfg = MediaCronConfig()
    assert isinstance(cfg.audiobook, AudiobookConfig)
    assert cfg.audiobook.enable_external_lookup is True
    assert cfg.audiobook.confidence_threshold == 0.85
    assert cfg.audiobook.cache.enabled is True
    assert cfg.audiobook.cache.ttl_seconds == 2592000
    assert cfg.audiobook.cache.cache_file == Path(".media-cron-cache/audiobook_cache.json")
    assert "openlibrary" in cfg.audiobook.providers
    assert cfg.audiobook.providers["openlibrary"].enabled is True
    assert cfg.audiobook.providers["openlibrary"].priority == 10
    assert "audnexus" in cfg.audiobook.providers
    assert cfg.audiobook.providers["audnexus"].enabled is False


def test_audiobook_yaml_loading(tmp_path: Path):
    yaml_file = tmp_path / "config.yaml"
    yaml_file.write_text("""
audiobook:
  enable_external_lookup: false
  confidence_threshold: 0.90
  cache:
    enabled: false
    ttl_seconds: 3600
    cache_file: "/tmp/custom_cache.json"
  providers:
    openlibrary:
      enabled: false
      priority: 50
      timeout_seconds: 12.0
    audnexus:
      enabled: true
      priority: 5
      timeout_seconds: 3.5
""")
    cfg = MediaCronConfig.load(config_path=yaml_file)
    assert cfg.audiobook.enable_external_lookup is False
    assert cfg.audiobook.confidence_threshold == 0.90
    assert cfg.audiobook.cache.enabled is False
    assert cfg.audiobook.cache.ttl_seconds == 3600
    assert cfg.audiobook.cache.cache_file == Path("/tmp/custom_cache.json")
    assert cfg.audiobook.providers["openlibrary"].enabled is False
    assert cfg.audiobook.providers["openlibrary"].priority == 50
    assert cfg.audiobook.providers["openlibrary"].timeout_seconds == 12.0
    assert cfg.audiobook.providers["audnexus"].enabled is True
    assert cfg.audiobook.providers["audnexus"].priority == 5
    assert cfg.audiobook.providers["audnexus"].timeout_seconds == 3.5


def test_audiobook_env_overrides(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MEDIA_CRON_AUDIOBOOK_ENABLE_LOOKUP", "false")
    monkeypatch.setenv("MEDIA_CRON_AUDIOBOOK_CONFIDENCE_THRESHOLD", "0.92")
    monkeypatch.setenv("MEDIA_CRON_AUDIOBOOK_CACHE_ENABLED", "false")
    monkeypatch.setenv("MEDIA_CRON_AUDIOBOOK_CACHE_TTL", "7200")
    monkeypatch.setenv("MEDIA_CRON_AUDIOBOOK_CACHE_FILE", "/var/cache/media.json")
    monkeypatch.setenv("MEDIA_CRON_OPENLIBRARY_ENABLED", "false")
    monkeypatch.setenv("MEDIA_CRON_AUDNEXUS_ENABLED", "true")
    monkeypatch.setenv("MEDIA_CRON_OPENLIBRARY_TIMEOUT", "8.5")
    monkeypatch.setenv("MEDIA_CRON_AUDNEXUS_TIMEOUT", "6.0")

    cfg = MediaCronConfig.load()
    assert cfg.audiobook.enable_external_lookup is False
    assert cfg.audiobook.confidence_threshold == 0.92
    assert cfg.audiobook.cache.enabled is False
    assert cfg.audiobook.cache.ttl_seconds == 7200
    assert cfg.audiobook.cache.cache_file == Path("/var/cache/media.json")
    assert cfg.audiobook.providers["openlibrary"].enabled is False
    assert cfg.audiobook.providers["audnexus"].enabled is True
    assert cfg.audiobook.providers["openlibrary"].timeout_seconds == 8.5
    assert cfg.audiobook.providers["audnexus"].timeout_seconds == 6.0
