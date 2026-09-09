from pathlib import Path

import pytest

from media_cron.config import (
    BooksConfig,
    MediaCronConfig,
)


def test_books_config_defaults():
    cfg = MediaCronConfig()
    assert isinstance(cfg.books, BooksConfig)
    assert cfg.books.enabled is True
    assert cfg.books.enable_external_lookup is True
    assert cfg.books.confidence_threshold == 0.85
    assert cfg.books.udc_lookup.enabled is False
    assert cfg.books.udc_lookup.min_confidence == 0.70
    assert cfg.books.udc_lookup.summary_table_path is None
    assert cfg.books.conversion.enabled is False
    assert cfg.books.conversion.preferred_engine == "calibre"
    assert cfg.books.conversion.timeout_seconds == 120
    assert cfg.books.conversion.retention_policy == "preserve"
    assert cfg.books.conversion.archive_dir is None
    assert cfg.books.conversion.inject_metadata is True
    assert cfg.books.cache.enabled is True
    assert cfg.books.cache.ttl_seconds == 2592000
    assert cfg.books.cache.cache_file == Path(".media-cron-cache/book_cache.json")
    assert "openlibrary" in cfg.books.providers
    assert cfg.books.providers["openlibrary"].enabled is True


def test_books_yaml_loading(tmp_path: Path):
    yaml_file = tmp_path / "config.yaml"
    yaml_file.write_text("""
books:
  enabled: true
  enable_external_lookup: false
  confidence_threshold: 0.90
  udc_lookup:
    enabled: true
    min_confidence: 0.80
    summary_table_path: "/custom/udc.json"
  conversion:
    enabled: true
    preferred_engine: "python_fallback"
    timeout_seconds: 60
    retention_policy: "archive"
    archive_dir: "/archive/books"
    inject_metadata: false
  cache:
    enabled: false
    ttl_seconds: 3600
    cache_file: "/tmp/custom_book_cache.json"
  providers:
    openlibrary:
      enabled: false
      priority: 50
      timeout_seconds: 12.0
""")
    cfg = MediaCronConfig.load(config_path=yaml_file)
    assert cfg.books.enabled is True
    assert cfg.books.enable_external_lookup is False
    assert cfg.books.confidence_threshold == 0.90
    assert cfg.books.udc_lookup.enabled is True
    assert cfg.books.udc_lookup.min_confidence == 0.80
    assert cfg.books.udc_lookup.summary_table_path == Path("/custom/udc.json")
    assert cfg.books.conversion.enabled is True
    assert cfg.books.conversion.preferred_engine == "python_fallback"
    assert cfg.books.conversion.timeout_seconds == 60
    assert cfg.books.conversion.retention_policy == "archive"
    assert cfg.books.conversion.archive_dir == Path("/archive/books")
    assert cfg.books.conversion.inject_metadata is False
    assert cfg.books.cache.enabled is False
    assert cfg.books.cache.ttl_seconds == 3600
    assert cfg.books.cache.cache_file == Path("/tmp/custom_book_cache.json")
    assert cfg.books.providers["openlibrary"].enabled is False
    assert cfg.books.providers["openlibrary"].priority == 50
    assert cfg.books.providers["openlibrary"].timeout_seconds == 12.0


def test_books_env_overrides(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MEDIA_CRON_BOOKS_ENABLED", "false")
    monkeypatch.setenv("MEDIA_CRON_BOOKS_EXTERNAL_LOOKUP", "false")
    monkeypatch.setenv("MEDIA_CRON_BOOKS_CONFIDENCE_THRESHOLD", "0.92")
    monkeypatch.setenv("MEDIA_CRON_BOOKS_UDC_ENABLED", "true")
    monkeypatch.setenv("MEDIA_CRON_BOOKS_CONVERT_EPUB", "true")
    monkeypatch.setenv("MEDIA_CRON_BOOKS_CONVERSION_ENGINE", "python_fallback")
    monkeypatch.setenv("MEDIA_CRON_BOOKS_RETENTION_POLICY", "replace")
    monkeypatch.setenv("MEDIA_CRON_BOOKS_ARCHIVE_DIR", "/opt/archive")
    monkeypatch.setenv("MEDIA_CRON_BOOKS_CACHE_FILE", "/var/cache/books.json")
    monkeypatch.setenv("MEDIA_CRON_BOOKS_CACHE_TTL", "7200")

    cfg = MediaCronConfig.load()
    assert cfg.books.enabled is False
    assert cfg.books.enable_external_lookup is False
    assert cfg.books.confidence_threshold == 0.92
    assert cfg.books.udc_lookup.enabled is True
    assert cfg.books.conversion.enabled is True
    assert cfg.books.conversion.preferred_engine == "python_fallback"
    assert cfg.books.conversion.retention_policy == "replace"
    assert cfg.books.conversion.archive_dir == Path("/opt/archive")
    assert cfg.books.cache.cache_file == Path("/var/cache/books.json")
    assert cfg.books.cache.ttl_seconds == 7200
