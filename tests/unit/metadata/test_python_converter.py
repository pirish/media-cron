import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from media_cron.metadata.converter import PythonFallbackConverter
from media_cron.metadata.models import BookMetadata


def test_python_converter_text_to_epub(tmp_path: Path):
    txt_file = tmp_path / "sample.txt"
    txt_file.write_text(
        "Chapter 1\nIt was a dark and stormy night.\n\nChapter 2\nThe sun came out.",
        encoding="utf-8",
    )

    epub_target = tmp_path / "sample.epub"
    converter = PythonFallbackConverter()
    metadata = BookMetadata(
        title="Stormy Night",
        author="Edward Bulwer",
        publication_year=1830,
    )

    converter.convert(txt_file, epub_target, metadata=metadata)
    assert epub_target.exists()
    assert epub_target.stat().st_size > 0

    with zipfile.ZipFile(epub_target, "r") as zf:
        # Check mimetype is first entry and uncompressed
        infolist = zf.infolist()
        assert infolist[0].filename == "mimetype"
        assert infolist[0].compress_type == zipfile.ZIP_STORED
        assert zf.read("mimetype") == b"application/epub+zip"

        # Check container.xml
        assert "META-INF/container.xml" in zf.namelist()

        # Check content.opf
        opf_data = zf.read("OEBPS/content.opf")
        root = ET.fromstring(opf_data)
        dc_title = root.find(".//{http://purl.org/dc/elements/1.1/}title")
        assert dc_title is not None and dc_title.text == "Stormy Night"
        dc_creator = root.find(".//{http://purl.org/dc/elements/1.1/}creator")
        assert dc_creator is not None and dc_creator.text == "Edward Bulwer"


def test_python_converter_fb2_to_epub(tmp_path: Path):
    fb2_file = tmp_path / "sample.fb2"
    fb2_content = """<?xml version="1.0" encoding="utf-8"?>
<FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0">
  <description>
    <title-info>
      <book-title>Foundation</book-title>
      <author><first-name>Isaac</first-name><last-name>Asimov</last-name></author>
    </title-info>
  </description>
  <body>
    <section>
      <title><p>Chapter 1</p></title>
      <p>Hari Seldon was sitting in his office.</p>
    </section>
  </body>
</FictionBook>"""
    fb2_file.write_text(fb2_content, encoding="utf-8")

    epub_target = tmp_path / "foundation.epub"
    converter = PythonFallbackConverter()
    metadata = BookMetadata(title="Foundation", author="Isaac Asimov")

    converter.convert(fb2_file, epub_target, metadata=metadata)
    assert epub_target.exists()

    with zipfile.ZipFile(epub_target, "r") as zf:
        assert zf.read("mimetype") == b"application/epub+zip"
        opf_data = zf.read("OEBPS/content.opf")
        assert b"Foundation" in opf_data
        assert b"Isaac Asimov" in opf_data
