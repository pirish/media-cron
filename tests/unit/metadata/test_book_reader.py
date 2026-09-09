import struct
import zipfile
from pathlib import Path

from media_cron.metadata.book_reader import BookMetadataReader


def test_read_epub_metadata(tmp_path: Path):
    epub_path = tmp_path / "sample.epub"
    with zipfile.ZipFile(epub_path, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip")
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
    <dc:title>Dune</dc:title>
    <dc:creator>Frank Herbert</dc:creator>
    <dc:identifier id="isbn">urn:isbn:9780441172719</dc:identifier>
    <dc:date>1965-08-01</dc:date>
    <dc:publisher>Chilton Books</dc:publisher>
    <dc:subject>Science Fiction</dc:subject>
    <meta name="calibre:series" content="Dune Chronicles"/>
    <meta name="calibre:series_index" content="1"/>
  </metadata>
</package>""",
        )

    reader = BookMetadataReader()
    metadata = reader.read_metadata(epub_path)
    assert metadata.title == "Dune"
    assert metadata.author == "Frank Herbert"
    assert metadata.isbn == "9780441172719"
    assert metadata.publication_year == 1965
    assert metadata.publisher == "Chilton Books"
    assert "Science Fiction" in metadata.subjects
    assert metadata.series_name == "Dune Chronicles"
    assert metadata.volume_number == "1"


def test_read_fb2_metadata(tmp_path: Path):
    fb2_path = tmp_path / "sample.fb2"
    fb2_content = """<?xml version="1.0" encoding="utf-8"?>
<FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0">
  <description>
    <title-info>
      <genre>sf_space</genre>
      <author>
        <first-name>Isaac</first-name>
        <last-name>Asimov</last-name>
      </author>
      <book-title>Foundation</book-title>
      <date>1951</date>
    </title-info>
  </description>
  <body></body>
</FictionBook>"""
    fb2_path.write_text(fb2_content, encoding="utf-8")

    reader = BookMetadataReader()
    metadata = reader.read_metadata(fb2_path)
    assert metadata.title == "Foundation"
    assert metadata.author == "Isaac Asimov"
    assert metadata.publication_year == 1951
    assert "sf_space" in metadata.subjects


def test_read_cbz_metadata(tmp_path: Path):
    cbz_path = tmp_path / "sample.cbz"
    with zipfile.ZipFile(cbz_path, "w") as zf:
        zf.writestr(
            "ComicInfo.xml",
            """<?xml version="1.0"?>
<ComicInfo>
  <Title>Days of Future Past</Title>
  <Series>The Uncanny X-Men</Series>
  <Number>141</Number>
  <Writer>Chris Claremont</Writer>
  <Year>1981</Year>
</ComicInfo>""",
        )

    reader = BookMetadataReader()
    metadata = reader.read_metadata(cbz_path)
    assert metadata.title == "Days of Future Past"
    assert metadata.author == "Chris Claremont"
    assert metadata.series_name == "The Uncanny X-Men"
    assert metadata.volume_number == "141"
    assert metadata.publication_year == 1981


def test_read_txt_filename_fallback(tmp_path: Path):
    txt_path = tmp_path / "Arthur C. Clarke - 2001 A Space Odyssey.txt"
    txt_path.write_text("Chapter 1: The Primeval Night\n...", encoding="utf-8")

    reader = BookMetadataReader()
    metadata = reader.read_metadata(txt_path)
    assert metadata.author == "Arthur C. Clarke"
    assert metadata.title == "2001 A Space Odyssey"


def test_read_mobi_synthetic_header(tmp_path: Path):
    # Construct a valid minimal Palm Database + MOBI header + EXTH records
    mobi_path = tmp_path / "test.mobi"

    title_bytes = b"Neuromancer"
    author_bytes = b"William Gibson"

    # Palm PDB header (78 bytes)
    pdb_header = bytearray(78)
    # Write name in first 32 bytes
    pdb_header[:11] = b"Neuromancer"
    num_records = 2
    pdb_header[76:78] = struct.pack(">H", num_records)

    # Record list: each entry is 8 bytes (offset: 4, attributes/id: 4)
    rec0_offset = 78 + (num_records * 8) + 2  # 78 + 16 + 2 = 96
    rec1_offset = rec0_offset + 500

    record_list = struct.pack(">IIII", rec0_offset, 0, rec1_offset, 0)
    padding = b"\x00\x00"

    # Record 0 content
    # PalmDOC header: 16 bytes
    palmdoc = struct.pack(">HHIHH", 1, 0, 4096, 1, 4096) + b"\x00\x00\x00\x00"

    # MOBI header: magic b"MOBI", length 232 bytes, type 2, encoding 65001 (utf-8)
    mobi_magic = b"MOBI"
    mobi_len = 232
    mobi_type = 2
    mobi_enc = 65001

    mobi_hdr = bytearray(mobi_len)
    mobi_hdr[0:4] = mobi_magic
    mobi_hdr[4:8] = struct.pack(">I", mobi_len)
    mobi_hdr[8:12] = struct.pack(">I", mobi_type)
    mobi_hdr[12:16] = struct.pack(">I", mobi_enc)

    # Full name offset relative to record 0
    # Place title after EXTH header
    full_name_offset = 16 + mobi_len + 128
    mobi_hdr[84:88] = struct.pack(">I", full_name_offset)
    mobi_hdr[88:92] = struct.pack(">I", len(title_bytes))
    # EXTH flags (bit 6 set)
    mobi_hdr[112:116] = struct.pack(">I", 0x40)

    # EXTH header
    exth_magic = b"EXTH"
    # 1 record: author (100)
    rec100 = struct.pack(">II", 100, 8 + len(author_bytes)) + author_bytes
    exth_len = 12 + len(rec100)
    # Pad EXTH to 4-byte boundary
    pad_len = (4 - (exth_len % 4)) % 4
    exth_data = (
        exth_magic + struct.pack(">II", exth_len + pad_len, 1) + rec100 + (b"\x00" * pad_len)
    )

    rec0 = palmdoc + mobi_hdr + exth_data
    # Pad until full_name_offset
    if len(rec0) < full_name_offset:
        rec0 += b"\x00" * (full_name_offset - len(rec0))
    rec0 += title_bytes

    with open(mobi_path, "wb") as f:
        f.write(pdb_header + record_list + padding + rec0)

    reader = BookMetadataReader()
    metadata = reader.read_metadata(mobi_path)
    assert metadata.title == "Neuromancer"
    assert metadata.author == "William Gibson"
