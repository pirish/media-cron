# Contract: Music Metadata Provider Interface

**Feature**: `005-music-organization`
**Date**: 2026-09-09
**Status**: Complete

---

## 1. Protocol Definition

Extends the existing `MetadataProviderProtocol` in `media_cron.metadata.base` to support music releases and tracklists:

```python
from typing import Protocol, runtime_checkable
from media_cron.metadata.models import MusicCatalogMatch


@runtime_checkable
class MusicMetadataProviderProtocol(Protocol):
    """Protocol for external music catalog providers (MusicBrainz, Discogs)."""

    @property
    def provider_name(self) -> str:
        """Return canonical provider identifier (e.g. 'musicbrainz', 'discogs')."""
        ...

    def search_release(
        self,
        artist: str,
        album: str,
        track_count: int | None = None,
        year: int | None = None,
        timeout_seconds: int = 10,
    ) -> list[MusicCatalogMatch]:
        """
        Query external catalog for matching music releases.

        Returns candidate matches sorted by relevance score.
        """
        ...
```
