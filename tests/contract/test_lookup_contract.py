from pathlib import Path

from media_cron.models import DiscoveredItem
from media_cron.plugins.base import LookupPlugin
from media_cron.plugins.lookup.audio import AudioTagLookup
from media_cron.plugins.lookup.book import BookMetaLookup
from media_cron.plugins.lookup.video import SceneVideoLookup


def test_lookup_plugins_satisfy_protocol(tmp_path: Path):
    lookups = [SceneVideoLookup(), AudioTagLookup(), BookMetaLookup()]
    for lookup in lookups:
        assert isinstance(lookup, LookupPlugin)
        assert bool(lookup.plugin_name)

    # Test handling classification
    video_item = DiscoveredItem(source_path=Path("video.mkv"), file_size=10, modified_time=0.0)
    audio_item = DiscoveredItem(source_path=Path("audio.mp3"), file_size=10, modified_time=0.0)
    book_item = DiscoveredItem(source_path=Path("book.epub"), file_size=10, modified_time=0.0)

    assert SceneVideoLookup().can_handle(video_item)
    assert not SceneVideoLookup().can_handle(audio_item)

    assert AudioTagLookup().can_handle(audio_item)
    assert not AudioTagLookup().can_handle(book_item)

    assert BookMetaLookup().can_handle(book_item)
    assert not BookMetaLookup().can_handle(video_item)
