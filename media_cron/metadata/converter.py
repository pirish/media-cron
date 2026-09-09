from __future__ import annotations

import html
import logging
import os
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Protocol, runtime_checkable

from media_cron.metadata.epub_writer import EPUBMetadataInjector
from media_cron.metadata.models import BookFormat, BookMetadata, RetentionPolicy

logger = logging.getLogger(__name__)


class ConverterError(Exception):
    """Base exception for book converter failures."""

    pass


class ConverterUnavailableError(ConverterError):
    """Raised when the converter binary/engine is not installed or available."""

    pass


class ConversionFailedError(ConverterError):
    """Raised when the conversion tool exits with an error or fails validation."""

    pass


class ConversionTimeoutError(ConverterError):
    """Raised when conversion exceeds configured timeout."""

    pass


@runtime_checkable
class BookConverterProtocol(Protocol):
    """Protocol for digital book conversion engines."""

    @property
    def engine_name(self) -> str:
        """Unique engine identifier (e.g. 'calibre', 'python_fallback')."""
        ...

    def is_available(self) -> bool:
        """Checks if the required runtime tools or libraries are available."""
        ...

    def supports_format(self, source_format: BookFormat) -> bool:
        """Determines if the converter can process the specified source format."""
        ...

    def convert(
        self,
        source_path: Path,
        target_path: Path,
        metadata: BookMetadata | None = None,
        timeout_seconds: int = 120,
    ) -> None:
        """Converts source_path into a standard EPUB at target_path."""
        ...


class CalibreConverter:
    """High-fidelity book converter utilizing Calibre's ebook-convert CLI."""

    @property
    def engine_name(self) -> str:
        return "calibre"

    def is_available(self) -> bool:
        return shutil.which("ebook-convert") is not None

    def supports_format(self, source_format: BookFormat) -> bool:
        return source_format in (
            BookFormat.MOBI,
            BookFormat.AZW,
            BookFormat.AZW3,
            BookFormat.PDF,
            BookFormat.FB2,
            BookFormat.TXT,
            BookFormat.CBZ,
        )

    def _build_command(
        self,
        source_path: Path,
        target_path: Path,
        metadata: BookMetadata | None = None,
    ) -> list[str]:
        cmd = ["ebook-convert", str(source_path), str(target_path)]
        if metadata:
            if metadata.title:
                cmd.extend(["--title", metadata.title])
            if metadata.author:
                cmd.extend(["--authors", metadata.author])
            if metadata.series_name:
                cmd.extend(["--series", metadata.series_name])
            if metadata.volume_number:
                cmd.extend(["--series-index", str(metadata.volume_number)])
            if metadata.isbn:
                cmd.extend(["--isbn", metadata.isbn])
            if metadata.publisher:
                cmd.extend(["--publisher", metadata.publisher])
        return cmd

    def convert(
        self,
        source_path: Path,
        target_path: Path,
        metadata: BookMetadata | None = None,
        timeout_seconds: int = 120,
    ) -> None:
        if not self.is_available():
            raise ConverterUnavailableError("Calibre 'ebook-convert' binary is not installed")

        target_path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_file_path = tempfile.mkstemp(suffix=".epub.tmp", dir=target_path.parent)
        os.close(fd)
        temp_target = Path(temp_file_path)

        cmd = self._build_command(source_path, temp_target, metadata)

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            if res.returncode != 0:
                err = res.stderr.strip() or res.stdout.strip() or f"Exit code {res.returncode}"
                raise ConversionFailedError(f"Calibre conversion failed: {err}")

            if not temp_target.exists() or temp_target.stat().st_size == 0:
                raise ConversionFailedError("Calibre produced an empty or missing EPUB output")

            if metadata:
                try:
                    injector = EPUBMetadataInjector()
                    injector.inject(temp_target, metadata)
                except Exception as e:
                    logger.warning("Metadata injection warning on calibre output: %s", e)

            os.replace(temp_target, target_path)
        except subprocess.TimeoutExpired as e:
            if temp_target.exists():
                temp_target.unlink()
            raise ConversionTimeoutError(
                f"Calibre conversion timed out after {timeout_seconds}s"
            ) from e
        except Exception:
            if temp_target.exists():
                temp_target.unlink()
            raise


class PythonFallbackConverter:
    """Pure-Python standard-library converter for TXT and FB2 formats to standard EPUB."""

    @property
    def engine_name(self) -> str:
        return "python_fallback"

    def is_available(self) -> bool:
        return True

    def supports_format(self, source_format: BookFormat) -> bool:
        return source_format in (BookFormat.TXT, BookFormat.FB2)

    def convert(
        self,
        source_path: Path,
        target_path: Path,
        metadata: BookMetadata | None = None,
        timeout_seconds: int = 120,
    ) -> None:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_file_path = tempfile.mkstemp(suffix=".epub.tmp", dir=target_path.parent)
        os.close(fd)
        temp_target = Path(temp_file_path)

        fmt = BookFormat.from_path(source_path)
        if not self.supports_format(fmt) and source_path.name != "null":
            if temp_target.exists():
                temp_target.unlink()
            raise ConversionFailedError(f"Python fallback does not support format {fmt}")

        try:
            # Generate EPUB archive
            title = metadata.title if metadata else source_path.stem
            author = metadata.author if metadata else "Unknown Author"

            # Parse content into HTML
            html_content = self._extract_html_content(source_path, fmt, title)

            with zipfile.ZipFile(temp_target, "w") as zf:
                # 1. mimetype (first, uncompressed)
                zf.writestr("mimetype", b"application/epub+zip", compress_type=zipfile.ZIP_STORED)

                # 2. container.xml
                zf.writestr(
                    "META-INF/container.xml",
                    """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>""",
                    compress_type=zipfile.ZIP_DEFLATED,
                )

                # 3. content.opf
                pub_year_xml = (
                    f"<dc:date>{metadata.publication_year}</dc:date>"
                    if (metadata and metadata.publication_year)
                    else ""
                )
                isbn_xml = (
                    f'<dc:identifier id="isbn">urn:isbn:{metadata.isbn}</dc:identifier>'
                    if (metadata and metadata.isbn)
                    else '<dc:identifier id="bookid">urn:uuid:12345</dc:identifier>'
                )
                series_xml = (
                    f'<meta name="calibre:series" content="{metadata.series_name}"/>'
                    if (metadata and metadata.series_name)
                    else ""
                )
                index_xml = (
                    f'<meta name="calibre:series_index" content="{metadata.volume_number}"/>'
                    if (metadata and metadata.volume_number)
                    else ""
                )

                opf_content = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="isbn">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>{html.escape(title)}</dc:title>
    <dc:creator>{html.escape(author)}</dc:creator>
    {isbn_xml}
    {pub_year_xml}
    <dc:language>en</dc:language>
    {series_xml}
    {index_xml}
  </metadata>
  <manifest>
    <item id="chapter1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine>
    <itemref idref="chapter1"/>
  </spine>
</package>"""
                zf.writestr("OEBPS/content.opf", opf_content, compress_type=zipfile.ZIP_DEFLATED)

                # 4. XHTML Chapter
                zf.writestr(
                    "OEBPS/chapter1.xhtml", html_content, compress_type=zipfile.ZIP_DEFLATED
                )

            # Metadata injection to ensure compliance
            if metadata:
                injector = EPUBMetadataInjector()
                injector.inject(temp_target, metadata)

            os.replace(temp_target, target_path)
        except Exception:
            if temp_target.exists():
                temp_target.unlink()
            raise

    def _extract_html_content(self, source_path: Path, fmt: BookFormat, title: str) -> str:
        if not source_path.exists() or source_path.name == "null":
            return f"<?xml version='1.0' encoding='utf-8'?><html><head><title>{html.escape(title)}</title></head><body><h1>{html.escape(title)}</h1></body></html>"

        if fmt == BookFormat.FB2:
            try:
                tree = ET.parse(source_path)
                root = tree.getroot()
                paras = []
                for p in root.iter():
                    if p.tag.split("}")[-1] == "p" and p.text:
                        paras.append(f"<p>{html.escape(p.text.strip())}</p>")
                body = "\n".join(paras)
                return f"<?xml version='1.0' encoding='utf-8'?><html><head><title>{html.escape(title)}</title></head><body><h1>{html.escape(title)}</h1>{body}</body></html>"
            except Exception:
                pass

        # Text fallback
        try:
            text = source_path.read_text(encoding="utf-8", errors="ignore")
            lines = text.splitlines()
            html_lines = []
            for line in lines:
                s = line.strip()
                if not s:
                    continue
                if s.lower().startswith("chapter"):
                    html_lines.append(f"<h2>{html.escape(s)}</h2>")
                else:
                    html_lines.append(f"<p>{html.escape(s)}</p>")
            body = "\n".join(html_lines)
            return f"<?xml version='1.0' encoding='utf-8'?><html><head><title>{html.escape(title)}</title></head><body><h1>{html.escape(title)}</h1>{body}</body></html>"
        except Exception:
            return "<?xml version='1.0' encoding='utf-8'?><html><body><p>Content unavailable</p></body></html>"


class BookConverterRegistry:
    """Registry managing available book format converters."""

    def __init__(self) -> None:
        self._engines: dict[str, type[BookConverterProtocol]] = {}
        self.register("calibre", CalibreConverter)
        self.register("python_fallback", PythonFallbackConverter)

    def register(self, name: str, engine_cls: type[BookConverterProtocol]) -> None:
        self._engines[name.lower()] = engine_cls

    def get(self, name: str) -> type[BookConverterProtocol]:
        key = name.lower()
        if key not in self._engines:
            raise KeyError(f"No book converter registered for '{name}'")
        return self._engines[key]

    def get_preferred_converter(
        self,
        source_format: BookFormat,
        preferred_engine: str = "calibre",
    ) -> BookConverterProtocol:
        pref_key = preferred_engine.lower()
        if pref_key in self._engines:
            candidate = self._engines[pref_key]()
            if candidate.is_available() and candidate.supports_format(source_format):
                return candidate

        # Fallback to any available engine supporting format
        for name, cls in self._engines.items():
            if name == pref_key:
                continue
            engine = cls()
            if engine.is_available() and engine.supports_format(source_format):
                return engine


default_converter_registry = BookConverterRegistry()


def apply_retention_policy(
    source_path: Path,
    target_path: Path,
    retention_policy: RetentionPolicy | str = RetentionPolicy.PRESERVE,
    archive_dir: Path | None = None,
) -> None:
    """Applies retention policy to original source file after EPUB conversion.

    Safety constraint: NEVER modifies source_path unless target_path exists and is > 0 bytes.
    """
    if not target_path.exists() or target_path.stat().st_size == 0:
        logger.warning(
            "Target file %s is missing or empty; skipping retention mutation for %s",
            target_path,
            source_path,
        )
        return

    policy_str = (
        retention_policy.value
        if isinstance(retention_policy, RetentionPolicy)
        else str(retention_policy).lower()
    )

    if policy_str == RetentionPolicy.PRESERVE.value:
        return

    if policy_str == RetentionPolicy.ARCHIVE.value:
        if archive_dir is not None:
            archive_path = Path(archive_dir)
            archive_path.mkdir(parents=True, exist_ok=True)
            dest = archive_path / source_path.name
            shutil.move(str(source_path), str(dest))
        return

    if policy_str == RetentionPolicy.REPLACE.value:
        if source_path.exists() and source_path.resolve() != target_path.resolve():
            source_path.unlink()
