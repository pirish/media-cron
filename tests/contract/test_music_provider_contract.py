from media_cron.metadata.base import MusicMetadataProviderProtocol
from media_cron.metadata.providers.discogs import DiscogsProvider
from media_cron.metadata.providers.musicbrainz import MusicBrainzProvider


def test_musicbrainz_provider_satisfies_protocol():
    mb = MusicBrainzProvider()
    assert isinstance(mb, MusicMetadataProviderProtocol)
    assert mb.provider_name == "musicbrainz"
    assert hasattr(mb, "search_release")


def test_discogs_provider_satisfies_protocol():
    discogs = DiscogsProvider()
    assert isinstance(discogs, MusicMetadataProviderProtocol)
    assert discogs.provider_name == "discogs"
    assert hasattr(discogs, "search_release")
