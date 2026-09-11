from pathlib import Path

from media_cron.review.heuristics import derive_category_hint


def test_derive_category_hint_movie():
    assert derive_category_hint([Path("Solaris.1972.1080p.mkv")]) == "movie"
    assert derive_category_hint([Path("movie_recording.mp4")]) == "movie"


def test_derive_category_hint_tv():
    assert derive_category_hint([Path("Westworld.S01E02.720p.mkv")]) == "tv"
    assert derive_category_hint([Path("Show.Name.1x05.HDTV.mp4")]) == "tv"


def test_derive_category_hint_music():
    assert derive_category_hint([Path("01 - Track.mp3")]) == "music"
    assert derive_category_hint([Path("Album/song.flac"), Path("Album/cover.jpg")]) == "music"


def test_derive_category_hint_audiobook():
    assert derive_category_hint([Path("Author - Title.m4b")]) == "audiobook"


def test_derive_category_hint_book():
    assert derive_category_hint([Path("Programming_in_Python.epub")]) == "book"
    assert derive_category_hint([Path("Manual.pdf")]) == "book"


def test_derive_category_hint_unknown():
    assert derive_category_hint([Path("random_data.bin")]) is None
    assert derive_category_hint([]) is None
