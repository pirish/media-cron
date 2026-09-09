from __future__ import annotations

import logging
import re
import struct
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from media_cron.metadata.models import BookFormat, BookMetadata

logger = logging.getLogger(__name__)


class BookMetadataReader:
    """Extracts embedded metadata and filename cues from diverse digital book formats."""

    def read_metadata(self, path: Path) -> BookMetadata:
        fmt = BookFormat.from_path(path)

        try:
            if fmt == BookFormat.EPUB:
                meta = self._read_epub(path)
                if meta:
                    return meta
            elif fmt in (BookFormat.MOBI, BookFormat.AZW, BookFormat.AZW3):
                meta = self._read_mobi(path)
                if meta:
                    return meta
            elif fmt == BookFormat.FB2:
                meta = self._read_fb2(path)
                if meta:
                    return meta
            elif fmt == BookFormat.CBZ:
                meta = self._read_cbz(path)
                if meta:
                    return meta
            elif fmt == BookFormat.PDF:
                meta = self._read_pdf(path)
                if meta:
                    return meta
        except Exception as e:
            logger.debug("Failed reading embedded metadata from %s: %s", path, e)

        # Fallback to filename heuristics
        return self._read_filename_fallback(path)

    def _read_filename_fallback(self, path: Path) -> BookMetadata:
        stem = path.stem
        year: int | None = None

        year_match = re.search(r"\((\d{4})\)", stem)
        if year_match:
            try:
                year = int(year_match.group(1))
            except ValueError:
                pass
            stem = re.sub(r"\(\d{4}\)", "", stem).strip()

        if " - " in stem:
            parts = stem.split(" - ", 1)
            author = parts[0].strip()
            title = parts[1].strip()
        elif "_-_" in stem:
            parts = stem.split("_-_", 1)
            author = parts[0].strip()
            title = parts[1].strip()
        else:
            author = "Unknown Author"
            title = stem.strip()

        return BookMetadata(
            title=title or path.stem,
            author=author or "Unknown Author",
            publication_year=year,
        )

    def _read_epub(self, path: Path) -> BookMetadata | None:
        with zipfile.ZipFile(path, "r") as zf:
            namelist = zf.namelist()
            if "META-INF/container.xml" not in namelist:
                return None

            container_xml = zf.read("META-INF/container.xml")
            c_root = ET.fromstring(container_xml)
            opf_path = None
            for elem in c_root.iter():
                if elem.tag.endswith("rootfile"):
                    opf_path = elem.attrib.get("full-path")
                    break

            if not opf_path or opf_path not in namelist:
                return None

            opf_xml = zf.read(opf_path)
            opf_root = ET.fromstring(opf_xml)

            title: str | None = None
            author: str | None = None
            isbn: str | None = None
            year: int | None = None
            publisher: str | None = None
            subjects: list[str] = []
            series_name: str | None = None
            volume_number: str | None = None
            description: str | None = None
            language: str | None = "en"

            for elem in opf_root.iter():
                tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                tag_lower = tag.lower()

                if tag_lower == "title" and elem.text and not title:
                    title = elem.text.strip()
                elif tag_lower == "creator" and elem.text and not author:
                    author = elem.text.strip()
                elif tag_lower == "publisher" and elem.text and not publisher:
                    publisher = elem.text.strip()
                elif tag_lower == "description" and elem.text and not description:
                    description = elem.text.strip()
                elif tag_lower == "language" and elem.text:
                    language = elem.text.strip()
                elif tag_lower == "subject" and elem.text:
                    s = elem.text.strip()
                    if s and s not in subjects:
                        subjects.append(s)
                elif tag_lower == "date" and elem.text and not year:
                    ym = re.search(r"\b(\d{4})\b", elem.text)
                    if ym:
                        year = int(ym.group(1))
                elif tag_lower == "identifier" and elem.text:
                    text_val = elem.text.strip()
                    clean_isbn = re.sub(r"^urn:isbn:", "", text_val, flags=re.IGNORECASE).strip()
                    norm_isbn = re.sub(r"[\s-]", "", clean_isbn)
                    if len(norm_isbn) in (10, 13) and (
                        elem.attrib.get("id") == "isbn"
                        or "isbn" in elem.attrib.get("scheme", "").lower()
                        or "urn:isbn:" in text_val.lower()
                    ):
                        isbn = norm_isbn
                    elif not isbn and len(norm_isbn) in (10, 13):
                        isbn = norm_isbn
                elif tag_lower == "meta":
                    name = elem.attrib.get("name", "").lower()
                    prop = elem.attrib.get("property", "").lower()
                    content = elem.attrib.get("content", "") or elem.text or ""
                    content = content.strip()

                    if name == "calibre:series" or prop == "belongs-to-collection":
                        series_name = content
                    elif name == "calibre:series_index" or prop == "group-position":
                        volume_number = content

            if not title:
                fallback = self._read_filename_fallback(path)
                title = fallback.title
                if not author:
                    author = fallback.author

            return BookMetadata(
                title=title or path.stem,
                author=author or "Unknown Author",
                series_name=series_name,
                volume_number=volume_number,
                publisher=publisher,
                publication_year=year,
                isbn=isbn,
                language=language,
                subjects=subjects,
                description=description,
            )

    def _read_fb2(self, path: Path) -> BookMetadata | None:
        tree = ET.parse(path)
        root = tree.getroot()

        title: str | None = None
        author_parts: list[str] = []
        year: int | None = None
        subjects: list[str] = []
        series_name: str | None = None
        volume_number: str | None = None
        publisher: str | None = None
        isbn: str | None = None

        for elem in root.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            tag_lower = tag.lower()

            if tag_lower == "book-title" and elem.text and not title:
                title = elem.text.strip()
            elif tag_lower == "genre" and elem.text:
                g = elem.text.strip()
                if g and g not in subjects:
                    subjects.append(g)
            elif tag_lower == "author" and not author_parts:
                first, middle, last, nick = "", "", "", ""
                for child in elem:
                    c_tag = child.tag.split("}")[-1].lower()
                    txt = (child.text or "").strip()
                    if c_tag == "first-name":
                        first = txt
                    elif c_tag == "middle-name":
                        middle = txt
                    elif c_tag == "last-name":
                        last = txt
                    elif c_tag == "nickname":
                        nick = txt
                names = [n for n in [first, middle, last] if n]
                if names:
                    author_parts.append(" ".join(names))
                elif nick:
                    author_parts.append(nick)
            elif tag_lower == "date" and elem.text and not year:
                ym = re.search(r"\b(\d{4})\b", elem.text)
                if ym:
                    year = int(ym.group(1))
            elif tag_lower == "sequence":
                if "name" in elem.attrib and not series_name:
                    series_name = elem.attrib["name"].strip()
                if "number" in elem.attrib and not volume_number:
                    volume_number = elem.attrib["number"].strip()
            elif tag_lower == "isbn" and elem.text and not isbn:
                isbn = re.sub(r"[\s-]", "", elem.text.strip())
            elif tag_lower == "publisher" and elem.text and not publisher:
                publisher = elem.text.strip()

        author = author_parts[0] if author_parts else "Unknown Author"
        if not title:
            fallback = self._read_filename_fallback(path)
            title = fallback.title
            if author == "Unknown Author":
                author = fallback.author

        return BookMetadata(
            title=title or path.stem,
            author=author,
            series_name=series_name,
            volume_number=volume_number,
            publisher=publisher,
            publication_year=year,
            isbn=isbn,
            subjects=subjects,
        )

    def _read_cbz(self, path: Path) -> BookMetadata | None:
        with zipfile.ZipFile(path, "r") as zf:
            namelist = zf.namelist()
            ci_path = next((n for n in namelist if n.lower().endswith("comicinfo.xml")), None)
            if not ci_path:
                return None

            xml_data = zf.read(ci_path)
            root = ET.fromstring(xml_data)

            title: str | None = None
            author: str | None = None
            series_name: str | None = None
            volume_number: str | None = None
            year: int | None = None
            subjects: list[str] = []

            for elem in root.iter():
                tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                tag_lower = tag.lower()
                val = (elem.text or "").strip()

                if tag_lower == "title" and val and not title:
                    title = val
                elif tag_lower in ("writer", "author") and val and not author:
                    author = val
                elif tag_lower == "series" and val and not series_name:
                    series_name = val
                elif tag_lower in ("number", "issue") and val and not volume_number:
                    volume_number = val
                elif tag_lower == "year" and val and not year:
                    try:
                        year = int(val)
                    except ValueError:
                        pass
                elif tag_lower == "genre" and val:
                    for g in val.split(","):
                        g_clean = g.strip()
                        if g_clean and g_clean not in subjects:
                            subjects.append(g_clean)

            if not title:
                fallback = self._read_filename_fallback(path)
                title = fallback.title
                if not author:
                    author = fallback.author

            return BookMetadata(
                title=title or path.stem,
                author=author or "Unknown Author",
                series_name=series_name,
                volume_number=volume_number,
                publication_year=year,
                subjects=subjects,
            )

    def _read_mobi(self, path: Path) -> BookMetadata | None:
        data = path.read_bytes()
        if len(data) < 78:
            return None

        # PDB Header (78 bytes)
        pdb_name = data[:32].split(b"\x00")[0].decode("latin1", errors="ignore").strip()
        num_records = struct.unpack(">H", data[76:78])[0]
        if num_records == 0 or len(data) < 78 + (num_records * 8):
            return None

        rec0_offset = struct.unpack(">I", data[78:82])[0]
        if rec0_offset >= len(data):
            return None

        rec0 = data[rec0_offset:]
        if len(rec0) < 16 + 132:
            return None

        # PalmDOC header: 16 bytes. MOBI header starts at offset 16 of record 0.
        mobi_magic = rec0[16:20]
        if mobi_magic != b"MOBI":
            # Check if anywhere in first 100 bytes
            m_idx = rec0.find(b"MOBI")
            if m_idx < 0:
                return BookMetadata(
                    title=pdb_name or path.stem,
                    author="Unknown Author",
                )
            mobi_start = m_idx
        else:
            mobi_start = 16

        mobi_len = struct.unpack(">I", rec0[mobi_start + 4 : mobi_start + 8])[0]
        full_name_offset = struct.unpack(">I", rec0[mobi_start + 84 : mobi_start + 88])[0]
        full_name_len = struct.unpack(">I", rec0[mobi_start + 88 : mobi_start + 92])[0]

        title: str | None = None
        if full_name_offset < len(rec0) and full_name_len > 0:
            title_bytes = rec0[full_name_offset : full_name_offset + full_name_len]
            title = title_bytes.decode("utf-8", errors="ignore").strip()

        if not title:
            title = pdb_name

        author: str | None = None
        isbn: str | None = None
        publisher: str | None = None
        subjects: list[str] = []
        year: int | None = None

        # EXTH flags check
        if mobi_start + 116 <= len(rec0):
            exth_flags = struct.unpack(">I", rec0[mobi_start + 112 : mobi_start + 116])[0]
            if (exth_flags & 0x40) != 0:
                exth_offset = mobi_start + mobi_len
                if exth_offset + 12 <= len(rec0) and rec0[exth_offset : exth_offset + 4] == b"EXTH":
                    _exth_len = struct.unpack(">I", rec0[exth_offset + 4 : exth_offset + 8])[0]
                    rec_count = struct.unpack(">I", rec0[exth_offset + 8 : exth_offset + 12])[0]
                    curr = exth_offset + 12

                    for _ in range(rec_count):
                        if curr + 8 > len(rec0):
                            break
                        rec_type = struct.unpack(">I", rec0[curr : curr + 4])[0]
                        rec_len = struct.unpack(">I", rec0[curr + 4 : curr + 8])[0]
                        if rec_len < 8 or curr + rec_len > len(rec0):
                            break
                        rec_data = rec0[curr + 8 : curr + rec_len]
                        val = rec_data.decode("utf-8", errors="ignore").strip()

                        if rec_type == 100 and val and not author:
                            author = val
                        elif rec_type == 101 and val and not publisher:
                            publisher = val
                        elif rec_type == 104 and val and not isbn:
                            isbn = re.sub(r"[\s-]", "", val)
                        elif rec_type == 105 and val:
                            if val not in subjects:
                                subjects.append(val)
                        elif rec_type == 106 and val and not year:
                            ym = re.search(r"\b(\d{4})\b", val)
                            if ym:
                                year = int(ym.group(1))

                        curr += rec_len

        return BookMetadata(
            title=title or path.stem,
            author=author or "Unknown Author",
            publisher=publisher,
            publication_year=year,
            isbn=isbn,
            subjects=subjects,
        )

    def _read_pdf(self, path: Path) -> BookMetadata | None:
        try:
            with open(path, "rb") as f:
                header = f.read(16384)
                f.seek(max(0, path.stat().st_size - 16384))
                trailer = f.read(16384)
            data = header + trailer
        except Exception:
            return None

        title: str | None = None
        author: str | None = None

        tm = re.search(rb"/Title\s*\(([^)]+)\)", data)
        if tm:
            title = tm.group(1).decode("latin1", errors="ignore").strip()

        am = re.search(rb"/Author\s*\(([^)]+)\)", data)
        if am:
            author = am.group(1).decode("latin1", errors="ignore").strip()

        if not title:
            return None

        return BookMetadata(
            title=title,
            author=author or "Unknown Author",
        )
