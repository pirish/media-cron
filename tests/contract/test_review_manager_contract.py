from pathlib import Path

from media_cron.review.base import ReviewManagerProtocol


class DummyReviewManager:
    """Dummy class conforming to ReviewManagerProtocol for contract testing."""

    @property
    def review_dir(self) -> Path:
        return Path("/tmp/review")

    def list_items(self, status=None):
        return []

    def get_item(self, item_id: str):
        raise FileNotFoundError(item_id)

    def stage_unrecognized(self, source_paths, config, failure_reasons=None, dry_run=False):
        return None

    def resolve_item(self, item_id: str, annotation, action, config, dry_run=False):
        return None

    def purge_items(self, older_than_days: int, dry_run=False):
        return []


def test_review_manager_protocol_conformance():
    dummy = DummyReviewManager()
    assert isinstance(dummy, ReviewManagerProtocol)
    assert dummy.review_dir == Path("/tmp/review")
    assert dummy.list_items() == []
    assert dummy.purge_items(7) == []
