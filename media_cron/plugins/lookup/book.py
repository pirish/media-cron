from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from media_cron.config import BooksConfig
from media_cron.metadata.book_identifier import BookIdentifier
from media_cron.metadata.converter import (
    BookConverterRegistry,
    apply_retention_policy,
    default_converter_registry,
)
from media_cron.metadata.epub_writer import EPUBMetadataInjector
from media_cron.metadata.models import BookFormat
from media_cron.models import DiscoveredItem, MediaAsset, MediaCategory
from media_cron.plugins.base import LookupPlugin
from media_cron.plugins.registry import default_registry

logger = logging.getLogger(__name__)

BOOK_EXTENSIONS = {
    ".epub",
    ".mobi",
    ".azw",
    ".azw3",
    ".kf8",
    ".pdf",
    ".fb2",
    ".cbz",
    ".cbr",
    ".txt",
}


class BookLookupPlugin(LookupPlugin):
    """Extracts digital book metadata and integrates automated catalog identification and conversion."""

    def __init__(
        self,
        identifier: BookIdentifier | None = None,
        converter_registry: BookConverterRegistry | None = None,
    ) -> None:
        self.identifier = identifier or BookIdentifier()
        self.converter_registry = converter_registry or default_converter_registry
        self.dry_run = False

    def configure(self, config: Any) -> None:
        if isinstance(config, BooksConfig):
            self.identifier.config = config
        elif hasattr(config, "books") and isinstance(config.books, BooksConfig):
            self.identifier.config = config.books
            if hasattr(config, "general") and hasattr(config.general, "dry_run"):
                self.dry_run = config.general.dry_run

    @property
    def plugin_name(self) -> str:
        return "book_meta"

    def can_handle(self, item: DiscoveredItem) -> bool:
        return item.source_path.suffix.lower() in BOOK_EXTENSIONS

    def enrich(self, item: DiscoveredItem) -> MediaAsset:
        path = item.source_path
        ext = path.suffix.lower()

        book_asset = self.identifier.identify(path=path)
        canonical = book_asset.canonical_metadata

        conv_cfg = getattr(self.identifier.config, "conversion", None)
        should_convert = bool(
            conv_cfg
            and getattr(conv_cfg, "enabled", False)
            and book_asset.format != BookFormat.EPUB
        )

        final_path = path
        final_ext = ext
        final_size = item.file_size

        if should_convert:
            target_epub = path.parent / f"{path.stem}.epub"
            if not self.dry_run:
                try:
                    pref_engine = getattr(conv_cfg, "preferred_engine", "calibre")
                    timeout_sec = int(getattr(conv_cfg, "timeout_seconds", 120))
                    converter = self.converter_registry.get_preferred_converter(
                        book_asset.format,
                        preferred_engine=pref_engine,
                    )
                    converter.convert(
                        source_path=path,
                        target_path=target_epub,
                        metadata=canonical,
                        timeout_seconds=timeout_sec,
                    )
                    self._apply_retention(path, target_epub, conv_cfg)
                except Exception as e:
                    logger.warning("Conversion failed for %s: %s", path, e)
                    # On conversion failure, preserve original file per FR-012/SC-004
                    target_epub = None

            if target_epub and (self.dry_run or target_epub.exists()):
                final_path = target_epub
                final_ext = ".epub"
                final_size = target_epub.stat().st_size if target_epub.exists() else item.file_size

        elif (
            book_asset.format == BookFormat.EPUB
            and conv_cfg
            and getattr(conv_cfg, "inject_metadata", True)
            and not self.dry_run
        ):
            try:
                injector = EPUBMetadataInjector()
                injector.inject(path, canonical)
                final_size = path.stat().st_size
            except Exception as e:
                logger.debug("Failed injecting metadata into existing EPUB %s: %s", path, e)

        return MediaAsset(
            path=final_path,
            category=MediaCategory.BOOK_EBOOK,
            raw_title=path.name,
            clean_title=canonical.title,
            extension=final_ext,
            file_size=final_size,
            author=canonical.author,
            year=canonical.publication_year,
            series_title=canonical.series_name,
            volume=canonical.volume_number,
            isbn=canonical.isbn,
            confidence=book_asset.confidence,
            identification_source=book_asset.match_source,
            udc_code=canonical.udc_code,
            is_valid=True,
        )

    def _apply_retention(self, source_path: Path, target_epub: Path, conv_cfg: Any) -> None:
        policy = getattr(conv_cfg, "retention_policy", "preserve")
        archive_dir = getattr(conv_cfg, "archive_dir", None)
        apply_retention_policy(
            source_path=source_path,
            target_path=target_epub,
            retention_policy=policy,
            archive_dir=archive_dir,
        )


# Backward-compatible alias
BookMetaLookup = BookLookupPlugin

default_registry.register_lookup("book_meta", BookLookupPlugin)
