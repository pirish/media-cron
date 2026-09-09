import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest

from media_cron.metadata.epub_writer import EPUBMetadataInjector
from media_cron.metadata.models import BookMetadata


def _create_minimal_epub(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        zf.writestr(
            "META-INF/container.xml",
            """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>""",
        )
        zf.writestr(
            "OEBPS/content.opf",
            """<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Original Title</dc:title>
    <dc:creator>Original Author</dc:creator>
  </metadata>
  <manifest>
    <item id="content" href="content.html" media-type="application/xhtml+xml"/>
  </manifest>
  <spine>
    <itemref idref="content"/>
  </spine>
</package>""",
        )
        zf.writestr("OEBPS/content.html", "<html><body><p>Hello world</p></body></html>")


def test_epub_metadata_injector_updates_metadata(tmp_path: Path):
    epub_path = tmp_path / "test.epub"
    _create_minimal_epub(epub_path)

    injector = EPUBMetadataInjector()
    new_meta = BookMetadata(
        title="Dune",
        author="Frank Herbert",
        series_name="Dune Chronicles",
        volume_number="1",
        isbn="9780441172719",
        publication_year=1965,
        udc_code="82-311.9",
        subjects=["Science Fiction"],
    )

    injector.inject(epub_path, new_meta)

    # Verify EPUB structure and injected metadata
    with zipfile.ZipFile(epub_path, "r") as zf:
        infolist = zf.infolist()
        assert infolist[0].filename == "mimetype"
        assert infolist[0].compress_type == zipfile.ZIP_STORED

        opf_data = zf.read("OEBPS/content.opf")
        root = ET.fromstring(opf_data)

        dc_ns = {"dc": "http://purl.org/dc/elements/1.1/"}
        assert root.find(".//dc:title", dc_ns).text == "Dune"
        assert root.find(".//dc:creator", dc_ns).text == "Frank Herbert"

        # Check ISBN
        identifiers = [e.text for e in root.findall(".//dc:identifier", dc_ns)]
        assert any("9780441172719" in (i or "") for i in identifiers)

        # Check UDC subject
        subjects = [e.text for e in root.findall(".//dc:subject", dc_ns)]
        assert "Science Fiction" in subjects
        assert any("UDC: 82-311.9" in (s or "") for s in subjects)


def test_epub_metadata_injector_validates_container(tmp_path: Path):
    corrupt_path = tmp_path / "corrupt.epub"
    corrupt_path.write_bytes(b"not an epub")

    injector = EPUBMetadataInjector()
    meta = BookMetadata(title="Test", author="Author")
    with pytest.raises((ValueError, zipfile.BadZipFile)):
        injector.inject(corrupt_path, meta)
