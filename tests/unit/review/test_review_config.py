from pathlib import Path

import pytest

from media_cron.config import MediaCronConfig, ReviewConfig


def test_review_config_defaults():
    cfg = MediaCronConfig()
    assert cfg.paths.review_dir is None
    assert isinstance(cfg.review, ReviewConfig)
    assert cfg.review.enabled is True
    assert cfg.review.max_age_days == 0


def test_review_config_from_yaml(tmp_path: Path):
    yaml_file = tmp_path / "config.yaml"
    yaml_file.write_text(
        """
paths:
  review_dir: /custom/review
review:
  enabled: false
  max_age_days: 30
"""
    )
    cfg = MediaCronConfig.load(yaml_file)
    assert cfg.paths.review_dir == Path("/custom/review")
    assert cfg.review.enabled is False
    assert cfg.review.max_age_days == 30


def test_review_config_from_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MEDIA_CRON_PATHS_REVIEW_DIR", "/env/review/dir")
    monkeypatch.setenv("MEDIA_CRON_REVIEW_ENABLED", "0")
    monkeypatch.setenv("MEDIA_CRON_REVIEW_MAX_AGE_DAYS", "14")

    cfg = MediaCronConfig.load()
    assert cfg.paths.review_dir == Path("/env/review/dir")
    assert cfg.review.enabled is False
    assert cfg.review.max_age_days == 14
