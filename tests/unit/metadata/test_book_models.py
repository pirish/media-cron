from pathlib import Path

from media_cron.metadata.models import (
    BookAsset,
    BookFormat,
    BookMetadata,
    ConversionJob,
    ConversionState,
    RetentionPolicy,
    UDCClassification,
)


def test_book_format_detection():
    assert BookFormat.from_path(Path("book.epub")) == BookFormat.EPUB
    assert BookFormat.from_path(Path("book.mobi")) == BookFormat.MOBI
    assert BookFormat.from_path(Path("book.azw")) == BookFormat.AZW
    assert BookFormat.from_path(Path("book.azw3")) == BookFormat.AZW3
    assert BookFormat.from_path(Path("book.kf8")) == BookFormat.AZW3
    assert BookFormat.from_path(Path("book.pdf")) == BookFormat.PDF
    assert BookFormat.from_path(Path("book.fb2")) == BookFormat.FB2
    assert BookFormat.from_path(Path("book.cbz")) == BookFormat.CBZ
    assert BookFormat.from_path(Path("book.txt")) == BookFormat.TXT
    assert BookFormat.from_path(Path("book.iso")) == BookFormat.UNKNOWN


def test_udc_classification_serialization():
    udc = UDCClassification(
        notation="82-311.9",
        description="Literature - Fiction - Science fiction",
        parent_notation="82-31",
        confidence=1.0,
        source="summary_table",
    )
    data = udc.to_dict()
    assert data["notation"] == "82-311.9"
    assert data["description"] == "Literature - Fiction - Science fiction"
    assert data["parent_notation"] == "82-31"

    restored = UDCClassification.from_dict(data)
    assert restored.notation == udc.notation
    assert restored.description == udc.description
    assert restored.confidence == udc.confidence


def test_book_metadata_serialization():
    meta = BookMetadata(
        title="Dune",
        author="Frank Herbert",
        series_name="Dune Chronicles",
        volume_number="1",
        publisher="Chilton Books",
        publication_year=1965,
        isbn="9780441172719",
        language="en",
        subjects=["Science Fiction", "Space Opera"],
        udc_code="82-311.9",
    )
    data = meta.to_dict()
    assert data["title"] == "Dune"
    assert data["author"] == "Frank Herbert"
    assert data["subjects"] == ["Science Fiction", "Space Opera"]

    restored = BookMetadata.from_dict(data)
    assert restored.title == "Dune"
    assert restored.isbn == "9780441172719"
    assert restored.udc_code == "82-311.9"


def test_book_asset_and_conversion_job():
    meta = BookMetadata(title="Dune", author="Frank Herbert")
    asset = BookAsset(
        path=Path("/media/books/Dune.mobi"),
        format=BookFormat.MOBI,
        file_size_bytes=1048576,
        local_metadata=meta,
        canonical_metadata=meta,
        confidence=0.95,
        match_source="openlibrary",
    )
    assert asset.format == BookFormat.MOBI
    assert not asset.is_already_standard

    job = ConversionJob(
        job_id="test-job-1",
        source_path=asset.path,
        source_format=asset.format,
        target_format=BookFormat.EPUB,
        temp_target_path=Path("/media/books/Dune.epub.tmp"),
        final_target_path=Path("/media/books/Dune.epub"),
        retention_policy=RetentionPolicy.PRESERVE,
    )
    assert job.state == ConversionState.PENDING
    job_dict = job.to_dict()
    assert job_dict["source_format"] == "mobi"
    assert job_dict["target_format"] == "epub"
    assert job_dict["retention_policy"] == "preserve"
