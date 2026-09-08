import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from media_cron.models import DiscoveredItem, MediaAsset, MediaCategory
from media_cron.plugins.base import LookupPlugin
from media_cron.plugins.registry import default_registry

BOOK_EXTENSIONS = {".epub", ".pdf", ".mobi", ".azw3", ".cbr", ".cbz"}


class BookMetaLookup(LookupPlugin):
    """Extracts e-book metadata from EPUB container or filename heuristics."""

    @property
    def plugin_name(self) -> str:
        return "book_meta"

    def can_handle(self, item: DiscoveredItem) -> bool:
        return item.source_path.suffix.lower() in BOOK_EXTENSIONS

    def _extract_epub_metadata(self, path: Path) -> tuple[str | None, str | None]:
        title, author = None, None
        try:
            with zipfile.ZipFile(path, "r") as z:
                # Find container.xml
                container_data = z.read("META-INF/container.xml")
                root = ET.fromstring(container_data)
                # Find rootfile path
                ns = {"n": "urn:oasis:names:tc:opendocument:xmlns:container"}
                rootfile = root.find(".//n:rootfile", ns)
                if rootfile is not None:
                    opf_path = rootfile.attrib.get("full-path")
                    if opf_path and opf_path in z.namelist():
                        opf_data = z.read(opf_path)
                        opf_root = ET.fromstring(opf_data)
                        dc_ns = {"dc": "http://purl.org/dc/elements/1.1/"}
                        title_elem = opf_root.find(".//dc:title", dc_ns)
                        if title_elem is not None and title_elem.text:
                            title = title_elem.text.strip()
                        creator_elem = opf_root.find(".//dc:creator", dc_ns)
                        if creator_elem is not None and creator_elem.text:
                            author = creator_elem.text.strip()
        except Exception:
            pass
        return title, author

    def enrich(self, item: DiscoveredItem) -> MediaAsset:
        path = item.source_path
        ext = path.suffix.lower()
        title: str | None = None
        author: str | None = None
        year: int | None = None

        if ext == ".epub" and path.exists() and item.file_size > 500:
            title, author = self._extract_epub_metadata(path)

        # Fallback to filename heuristics: "Author - Title (Year)"
        if not title:
            stem = path.stem
            # Check year
            year_match = re.search(r"\((\d{4})\)", stem)
            if year_match:
                year = int(year_match.group(1))
                stem = re.sub(r"\(\d{4}\)", "", stem).strip()

            parts = stem.split(" - ")
            if len(parts) >= 2:
                author = re.sub(r"[._]", " ", parts[0]).strip()
                title = re.sub(r"[._]", " ", " - ".join(parts[1:])).strip()
            else:
                title = re.sub(r"[._]", " ", stem).strip()

        return MediaAsset(
            path=path,
            category=MediaCategory.BOOK_EBOOK,
            raw_title=path.name,
            clean_title=title or path.stem,
            extension=ext,
            file_size=item.file_size,
            author=author,
            year=year,
            is_valid=True,
        )


default_registry.register_lookup("book_meta", BookMetaLookup)
