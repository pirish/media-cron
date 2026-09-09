from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import media_cron.metadata.providers  # noqa: F401
from media_cron.config import BooksConfig
from media_cron.metadata.base import (
    MetadataProviderRegistry,
    ProviderError,
    default_provider_registry,
)
from media_cron.metadata.book_reader import BookMetadataReader
from media_cron.metadata.cache import MetadataCache
from media_cron.metadata.models import (
    BookAsset,
    BookFormat,
    BookMetadata,
    MetadataMatch,
)
from media_cron.metadata.scorer import ConfidenceScorer
from media_cron.metadata.udc import UDCResolver

logger = logging.getLogger(__name__)


class BookIdentifier:
    """Coordinates local book tag extraction, caching, external provider lookup, and confidence scoring."""

    def __init__(
        self,
        config: BooksConfig | None = None,
        registry: MetadataProviderRegistry | None = None,
        cache: MetadataCache | None = None,
        scorer: ConfidenceScorer | None = None,
        reader: BookMetadataReader | None = None,
        udc_resolver: Any | None = None,
    ) -> None:
        self._explicit_cache = cache
        self.registry = registry or default_provider_registry
        self.scorer = scorer or ConfidenceScorer()
        self.reader = reader or BookMetadataReader()
        self.udc_resolver = udc_resolver or UDCResolver()
        self.config = config or BooksConfig()

        self._last_request_time: dict[str, float] = {}

        # Telemetry counters
        self.total_books: int = 0
        self.identified_external: int = 0
        self.identified_local_only: int = 0
        self.cache_hits: int = 0
        self.cache_misses: int = 0
        self.provider_breakdown: dict[str, int] = {}
        self.confidences: list[float] = []

    @property
    def config(self) -> BooksConfig:
        return self._config

    @config.setter
    def config(self, new_config: BooksConfig) -> None:
        self._config = new_config
        if self._explicit_cache is not None:
            self.cache = self._explicit_cache
        else:
            cache_enabled = False
            cache_file = Path(".media-cron-cache") / "book_cache.json"
            ttl_seconds = 2592000
            if hasattr(self._config, "cache") and self._config.cache is not None:
                if isinstance(self._config.cache, dict):
                    cache_enabled = bool(self._config.cache.get("enabled", True))
                    cache_file = Path(self._config.cache.get("cache_file", cache_file))
                    ttl_seconds = int(self._config.cache.get("ttl_seconds", ttl_seconds))
                else:
                    cache_enabled = getattr(self._config.cache, "enabled", True)
                    cache_file = getattr(self._config.cache, "cache_file", cache_file)
                    ttl_seconds = getattr(self._config.cache, "ttl_seconds", ttl_seconds)

            if cache_enabled:
                self.cache = MetadataCache(cache_file=cache_file, default_ttl=ttl_seconds)
            else:
                self.cache = None

    def get_summary(self) -> dict[str, Any]:
        """Returns structured summary telemetry for all books identified in this session."""
        avg_conf = (
            round(sum(self.confidences) / len(self.confidences), 2) if self.confidences else 0.0
        )
        return {
            "total_books": self.total_books,
            "identified_external": self.identified_external,
            "identified_local_only": self.identified_local_only,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "provider_breakdown": dict(self.provider_breakdown),
            "average_confidence": avg_conf,
        }

    def _enforce_rate_limit(self, provider_name: str, delay: float) -> None:
        if delay <= 0:
            return
        last = self._last_request_time.get(provider_name)
        if last is not None:
            elapsed = time.time() - last
            if elapsed < delay:
                time.sleep(delay - elapsed)
        self._last_request_time[provider_name] = time.time()

    def identify(
        self,
        local_metadata: BookMetadata | None = None,
        path: Path | None = None,
    ) -> BookAsset:
        self.total_books += 1

        # Extract local metadata if not supplied
        if local_metadata is None:
            if path is not None:
                local_metadata = self.reader.read_metadata(path)
            else:
                local_metadata = BookMetadata(title="Unknown Title", author="Unknown Author")

        format_code = BookFormat.from_path(path) if path else BookFormat.UNKNOWN
        file_size = path.stat().st_size if (path and path.exists()) else 0

        has_author = bool(local_metadata.author and local_metadata.author != "Unknown Author")
        has_title = bool(
            local_metadata.title and local_metadata.title != (path.stem if path else "")
        )

        fallback_source = "local_tag" if (has_author or has_title) else "filename"
        fallback_confidence = 0.75 if fallback_source == "local_tag" else 0.50

        # Offline / disabled external lookup check
        if not self.config.enable_external_lookup:
            self.identified_local_only += 1
            self.confidences.append(fallback_confidence)
            asset = BookAsset(
                path=path or Path("unknown"),
                format=format_code,
                file_size_bytes=file_size,
                local_metadata=local_metadata,
                canonical_metadata=local_metadata,
                confidence=fallback_confidence,
                match_source=fallback_source,
            )
            self._apply_udc_if_enabled(asset)
            return asset

        # Check providers
        sorted_providers = sorted(
            [p for p in self.config.providers.values() if p.enabled],
            key=lambda x: x.priority,
        )

        if not sorted_providers:
            self.identified_local_only += 1
            self.confidences.append(fallback_confidence)
            asset = BookAsset(
                path=path or Path("unknown"),
                format=format_code,
                file_size_bytes=file_size,
                local_metadata=local_metadata,
                canonical_metadata=local_metadata,
                confidence=fallback_confidence,
                match_source=fallback_source,
            )
            self._apply_udc_if_enabled(asset)
            return asset

        best_match: MetadataMatch | None = None
        threshold = self.config.confidence_threshold
        query_title = local_metadata.title
        query_author = local_metadata.author if local_metadata.author != "Unknown Author" else None

        for prov_cfg in sorted_providers:
            p_name = prov_cfg.provider_name
            match_candidate: MetadataMatch | None = None

            # 1. Cache check
            if self.cache:
                match_candidate = self.cache.get(p_name, query_title, query_author)
                if match_candidate is not None:
                    self.cache_hits += 1

            # 2. Live provider lookup
            if match_candidate is None:
                if self.cache:
                    self.cache_misses += 1
                try:
                    prov_cls = self.registry.get(p_name)
                    try:
                        prov_inst = prov_cls(scorer=self.scorer)
                    except TypeError:
                        prov_inst = prov_cls()

                    self._enforce_rate_limit(p_name, prov_cfg.rate_limit_delay)
                    candidates = prov_inst.search(
                        title=query_title, author=query_author, config=prov_cfg
                    )
                    match_candidate = candidates[0] if candidates else None

                    if self.cache:
                        ttl = (
                            self.config.cache.ttl_seconds
                            if hasattr(self.config, "cache")
                            else 2592000
                        )
                        self.cache.put(
                            provider=p_name,
                            title=query_title,
                            author=query_author,
                            match=match_candidate,
                            ttl_seconds=ttl,
                        )
                except ProviderError as e:
                    logger.warning("Provider '%s' error: %s", p_name, e)
                    continue
                except Exception as e:
                    logger.warning("Unexpected error querying provider '%s': %s", p_name, e)
                    continue

            if match_candidate is not None:
                if match_candidate.confidence <= 0.0:
                    match_candidate.confidence = self.scorer.compute_confidence(
                        query_title=query_title,
                        query_author=query_author,
                        candidate_title=match_candidate.title,
                        candidate_author=match_candidate.author,
                    )

                if match_candidate.confidence >= threshold:
                    best_match = match_candidate
                    break
                elif match_candidate.confidence >= 0.60:
                    if best_match is None or match_candidate.confidence > best_match.confidence:
                        best_match = match_candidate

        # Resolve canonical metadata based on confidence
        if best_match is not None and best_match.confidence >= threshold:
            self.identified_external += 1
            self.provider_breakdown[best_match.provider] = (
                self.provider_breakdown.get(best_match.provider, 0) + 1
            )
            self.confidences.append(best_match.confidence)

            merged_subjects = list(
                dict.fromkeys(local_metadata.subjects + (best_match.subjects or []))
            )
            canonical = BookMetadata(
                title=best_match.title,
                author=best_match.author or local_metadata.author,
                series_name=best_match.series or local_metadata.series_name,
                volume_number=best_match.volume or local_metadata.volume_number,
                publisher=local_metadata.publisher,
                publication_year=best_match.year or local_metadata.publication_year,
                isbn=best_match.isbn or local_metadata.isbn,
                language=local_metadata.language,
                subjects=merged_subjects,
                description=local_metadata.description,
                udc_code=best_match.udc_code or local_metadata.udc_code,
            )
            asset = BookAsset(
                path=path or Path("unknown"),
                format=format_code,
                file_size_bytes=file_size,
                local_metadata=local_metadata,
                canonical_metadata=canonical,
                confidence=best_match.confidence,
                match_source=best_match.provider,
            )
            self._apply_udc_if_enabled(asset)
            return asset

        elif best_match is not None and best_match.confidence >= 0.60:
            # Below 85% threshold: retain local author and title, only enrich missing fields
            self.identified_local_only += 1
            self.confidences.append(fallback_confidence)

            merged_subjects = list(
                dict.fromkeys(local_metadata.subjects + (best_match.subjects or []))
            )
            canonical = BookMetadata(
                title=local_metadata.title,
                author=local_metadata.author,
                series_name=local_metadata.series_name or best_match.series,
                volume_number=local_metadata.volume_number or best_match.volume,
                publisher=local_metadata.publisher,
                publication_year=local_metadata.publication_year or best_match.year,
                isbn=local_metadata.isbn or best_match.isbn,
                language=local_metadata.language,
                subjects=merged_subjects,
                description=local_metadata.description,
                udc_code=local_metadata.udc_code or best_match.udc_code,
            )
            asset = BookAsset(
                path=path or Path("unknown"),
                format=format_code,
                file_size_bytes=file_size,
                local_metadata=local_metadata,
                canonical_metadata=canonical,
                confidence=fallback_confidence,
                match_source=fallback_source,
            )
            self._apply_udc_if_enabled(asset)
            return asset

        else:
            self.identified_local_only += 1
            self.confidences.append(fallback_confidence)
            asset = BookAsset(
                path=path or Path("unknown"),
                format=format_code,
                file_size_bytes=file_size,
                local_metadata=local_metadata,
                canonical_metadata=local_metadata,
                confidence=fallback_confidence,
                match_source=fallback_source,
            )
            self._apply_udc_if_enabled(asset)
            return asset

    def _apply_udc_if_enabled(self, asset: BookAsset) -> None:
        if (
            self.udc_resolver is not None
            and hasattr(self.config, "udc_lookup")
            and getattr(self.config.udc_lookup, "enabled", False)
        ):
            try:
                udc_result = self.udc_resolver.resolve(asset.canonical_metadata)
                if udc_result:
                    asset.udc_classification = udc_result
                    asset.canonical_metadata.udc_code = udc_result.notation
            except Exception as e:
                logger.debug("UDC resolution error: %s", e)
