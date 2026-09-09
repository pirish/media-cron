from media_cron.metadata.models import BookMetadata
from media_cron.metadata.udc import UDCResolver


def test_udc_resolver_exact_subject_match():
    resolver = UDCResolver()
    # Science Fiction -> 82-311.9 (deepest match)
    res = resolver.resolve(subjects=["Science Fiction", "Space Opera"])
    assert res is not None
    assert res.notation == "82-311.9"
    assert res.confidence == 1.0
    assert "Science fiction" in res.description

    # Fantasy -> 82-312.9
    res_fan = resolver.resolve(subjects=["Epic Fantasy", "Magic"])
    assert res_fan is not None
    assert res_fan.notation == "82-312.9"


def test_udc_resolver_parent_category_match():
    resolver = UDCResolver()
    # General fiction -> 82-31
    res = resolver.resolve(subjects=["Fiction", "Novels"])
    assert res is not None
    assert res.notation == "82-31"


def test_udc_resolver_dewey_crosswalk_fallback():
    resolver = UDCResolver()
    # No matching subjects, but Dewey hint 813.54 -> 82-31
    res = resolver.resolve(subjects=["Unknown Genre"], classification_hints=["813.54"])
    assert res is not None
    assert res.notation == "82-31"
    assert res.source == "dewey_crosswalk"

    # Dewey hint 510 -> 5
    res_math = resolver.resolve(subjects=[], classification_hints=["510"])
    assert res_math is not None
    assert res_math.notation == "5"


def test_udc_resolver_unmatched_graceful_none():
    resolver = UDCResolver()
    res = resolver.resolve(subjects=["Obscure topic completely unrelated"])
    assert res is None


def test_udc_resolver_book_metadata_input():
    resolver = UDCResolver()
    meta = BookMetadata(
        title="Dune",
        author="Frank Herbert",
        subjects=["Science Fiction", "Adventure"],
    )
    res = resolver.resolve(meta)
    assert res is not None
    assert res.notation == "82-311.9"
