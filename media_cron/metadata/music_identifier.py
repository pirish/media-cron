from __future__ import annotations

import logging

from media_cron.config import MusicConfig
from media_cron.metadata.base import MusicMetadataProviderProtocol
from media_cron.metadata.cache import MusicMetadataCache
from media_cron.metadata.models import MusicCatalogMatch
from media_cron.metadata.providers.discogs import DiscogsProvider
from media_cron.metadata.providers.musicbrainz import MusicBrainzProvider

logger = logging.getLogger(__name__)


class MusicIdentifier:
    """Coordinates local cache, external provider cascade (MusicBrainz -> Discogs), and confidence resolution."""

    def __init__(
        self,
        config: MusicConfig | None = None,
        cache: MusicMetadataCache | None = None,
        primary_provider: MusicMetadataProviderProtocol | None = None,
        fallback_provider: MusicMetadataProviderProtocol | None = None,
    ) -> None:
        self.config = config or MusicConfig()
        cache_file = self.config.cache.cache_file if self.config.cache else None
        self.cache = cache or MusicMetadataCache(cache_file=cache_file)
        self.primary_provider = primary_provider or MusicBrainzProvider()
        self.fallback_provider = fallback_provider or (
            DiscogsProvider(token=self.config.discogs_token) if self.config.discogs_token else None
        )

    def identify(
        self,
        artist: str,
        album: str,
        track_count: int | None = None,
        year: int | None = None,
    ) -> MusicCatalogMatch | None:
        """Queries providers in cascade order, returning the highest-confidence match exceeding threshold."""
        if not self.config.enable_external_lookup:
            return None

        threshold = self.config.confidence_threshold

        # 1. Check primary provider cache
        raw_p_name = getattr(self.primary_provider, "provider_name", None)
        p_name = raw_p_name if isinstance(raw_p_name, str) else "musicbrainz"
        cached = self.cache.get_match(p_name, artist, album)
        if cached and cached.confidence >= threshold:
            return cached

        # 2. Query primary provider
        try:
            matches = self.primary_provider.search_release(
                artist=artist,
                album=album,
                track_count=track_count,
                year=year,
            )
            if matches:
                self.cache.put(p_name, artist, album, matches=matches)
                top = matches[0]
                if top.confidence >= threshold:
                    return top
        except Exception as e:
            logger.debug(f"Primary music provider '{p_name}' failed: {e}")

        # 3. Check fallback provider
        if self.fallback_provider:
            raw_fb_name = getattr(self.fallback_provider, "provider_name", None)
            fb_name = raw_fb_name if isinstance(raw_fb_name, str) else "discogs"
            cached_fb = self.cache.get_match(fb_name, artist, album)
            if cached_fb and cached_fb.confidence >= threshold:
                return cached_fb

            try:
                fb_matches = self.fallback_provider.search_release(
                    artist=artist,
                    album=album,
                    track_count=track_count,
                    year=year,
                )
                if fb_matches:
                    self.cache.put(fb_name, artist, album, matches=fb_matches)
                    top_fb = fb_matches[0]
                    if top_fb.confidence >= threshold:
                        return top_fb
            except Exception as e:
                logger.debug(f"Fallback music provider '{fb_name}' failed: {e}")

        return None
