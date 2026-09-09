import logging
import re
import time
from pathlib import Path
from typing import Any

from media_cron.config import AudiobookConfig
from media_cron.metadata.base import (
    MetadataProviderRegistry,
    ProviderError,
    default_provider_registry,
)
from media_cron.metadata.cache import MetadataCache
from media_cron.metadata.models import MetadataMatch
from media_cron.metadata.scorer import ConfidenceScorer

logger = logging.getLogger(__name__)


class AudiobookIdentifier:
    """Coordinates local tag extraction, response caching, provider querying, and confidence evaluation."""

    def __init__(
        self,
        config: AudiobookConfig | None = None,
        registry: MetadataProviderRegistry | None = None,
        cache: MetadataCache | None = None,
        scorer: ConfidenceScorer | None = None,
    ) -> None:
        self._explicit_cache = cache
        self.registry = registry or default_provider_registry
        self.scorer = scorer or ConfidenceScorer()
        self.config = config or AudiobookConfig()

        self._last_request_time: dict[str, float] = {}

        # Telemetry counters
        self.total_audiobooks: int = 0
        self.identified_external: int = 0
        self.identified_local_only: int = 0
        self.cache_hits: int = 0
        self.cache_misses: int = 0
        self.provider_breakdown: dict[str, int] = {}
        self.confidences: list[float] = []

    @property
    def config(self) -> AudiobookConfig:
        return self._config

    @config.setter
    def config(self, new_config: AudiobookConfig) -> None:
        self._config = new_config
        if self._explicit_cache is not None:
            self.cache = self._explicit_cache
        else:
            cache_enabled = False
            cache_file = Path(".media-cron-cache") / "audiobook_cache.json"
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
        """Returns structured summary telemetry for all audiobooks identified in this session."""
        avg_conf = (
            round(sum(self.confidences) / len(self.confidences), 2) if self.confidences else 0.0
        )
        return {
            "total_audiobooks": self.total_audiobooks,
            "identified_external": self.identified_external,
            "identified_local_only": self.identified_local_only,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "provider_breakdown": dict(self.provider_breakdown),
            "average_confidence": avg_conf,
        }

    def parse_filename(self, stem: str) -> tuple[str, str | None]:
        """Heuristically extracts candidate (title, author) from a filename stem."""
        # Strip leading track numbers like "01 - ", "01. ", "01 "
        s = re.sub(r"^\d+[\s._-]+", "", stem).strip()
        if " - " in s:
            parts = s.split(" - ", 1)
            # Typically "Author - Title"
            return parts[1].strip(), parts[0].strip()
        return s.strip(), None

    def _enforce_rate_limit(self, provider_name: str, delay: float) -> None:
        """Enforces minimum interval between outbound requests to an external provider."""
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
        title: str | None = None,
        author: str | None = None,
        year: int | None = None,
        has_local_tags: bool = False,
        path: Path | None = None,
    ) -> MetadataMatch:
        """Identifies an audiobook using local cues, cached results, or sequential provider lookup."""
        self.total_audiobooks += 1

        # Derive title/author from filename if not provided
        if not title and path:
            parsed_title, parsed_author = self.parse_filename(path.stem)
            title = parsed_title or path.stem
            if not author:
                author = parsed_author

        resolved_title = title or (path.stem if path else "Unknown Title")
        resolved_author = author

        fallback_source = "local_tag" if has_local_tags else "filename"
        fallback_confidence = 0.75 if has_local_tags else 0.50

        local_fallback = MetadataMatch(
            title=resolved_title,
            author=resolved_author or "Unknown Author",
            year=year,
            provider=fallback_source,
            confidence=fallback_confidence,
        )

        # 1. Offline / local-only mode check
        if not self.config.enable_external_lookup:
            self.identified_local_only += 1
            self.confidences.append(local_fallback.confidence)
            return local_fallback

        # 2. Sequential provider cascade
        sorted_providers = sorted(
            [p for p in self.config.providers.values() if p.enabled],
            key=lambda x: x.priority,
        )

        if not sorted_providers:
            self.identified_local_only += 1
            self.confidences.append(local_fallback.confidence)
            return local_fallback

        best_match: MetadataMatch | None = None
        threshold = self.config.confidence_threshold

        for prov_cfg in sorted_providers:
            p_name = prov_cfg.provider_name
            match_candidate: MetadataMatch | None = None

            # Check cache first
            if self.cache:
                match_candidate = self.cache.get(p_name, resolved_title, resolved_author)
                if match_candidate is not None:
                    self.cache_hits += 1

            # Live lookup on cache miss
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
                        title=resolved_title, author=resolved_author, config=prov_cfg
                    )
                    match_candidate = candidates[0] if candidates else None

                    # Cache candidate result
                    if self.cache:
                        self.cache.put(
                            provider=p_name,
                            title=resolved_title,
                            author=resolved_author,
                            match=match_candidate,
                            ttl_seconds=self.config.cache.ttl_seconds,
                        )
                except ProviderError as e:
                    logger.warning("Provider '%s' error: %s", p_name, e)
                    continue
                except Exception as e:
                    logger.warning(
                        "Unexpected error during lookup with provider '%s': %s", p_name, e
                    )
                    continue

            if match_candidate is not None:
                if match_candidate.confidence <= 0.0:
                    match_candidate.confidence = self.scorer.compute_confidence(
                        query_title=resolved_title,
                        query_author=resolved_author,
                        candidate_title=match_candidate.title,
                        candidate_author=match_candidate.author,
                    )

                if match_candidate.confidence >= threshold:
                    best_match = match_candidate
                    break
                elif match_candidate.confidence >= 0.60:
                    if best_match is None or match_candidate.confidence > best_match.confidence:
                        best_match = match_candidate

        # 3. Resolve final match metadata
        if best_match is not None and best_match.confidence >= threshold:
            self.identified_external += 1
            self.provider_breakdown[best_match.provider] = (
                self.provider_breakdown.get(best_match.provider, 0) + 1
            )
            self.confidences.append(best_match.confidence)
            return MetadataMatch(
                title=best_match.title,
                author=best_match.author or resolved_author or "Unknown Author",
                year=best_match.year or year,
                narrator=best_match.narrator,
                series=best_match.series,
                volume=best_match.volume,
                work_id=best_match.work_id,
                provider=best_match.provider,
                confidence=best_match.confidence,
                raw_response=best_match.raw_response,
            )

        elif best_match is not None and best_match.confidence >= 0.60:
            # Partial enrichment: preserve local title & author, adopt non-conflicting attributes
            self.identified_local_only += 1
            self.confidences.append(local_fallback.confidence)
            return MetadataMatch(
                title=resolved_title,
                author=resolved_author or best_match.author or "Unknown Author",
                year=year or best_match.year,
                narrator=best_match.narrator,
                series=best_match.series,
                volume=best_match.volume,
                work_id=best_match.work_id,
                provider=fallback_source,
                confidence=local_fallback.confidence,
                raw_response=best_match.raw_response,
            )

        else:
            self.identified_local_only += 1
            self.confidences.append(local_fallback.confidence)
            return local_fallback
