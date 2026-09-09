from pathlib import Path
from unittest.mock import MagicMock, patch

from media_cron.metadata.models import MusicFormat
from media_cron.metadata.music_reader import MusicMetadataReader


def test_music_reader_with_embedded_tags(tmp_path: Path):
    audio_file = tmp_path / "song.flac"
    audio_file.write_bytes(b"dummy flac header")

    mock_tag = MagicMock(
        title="Time",
        artist="Pink Floyd",
        album="The Dark Side of the Moon",
        albumartist="Pink Floyd",
        track=4,
        disc=1,
        year=1973,
        genre="Progressive Rock",
        duration=425.0,
        bitrate=920,
    )

    with patch("media_cron.metadata.music_reader.TinyTag.get", return_value=mock_tag):
        reader = MusicMetadataReader()
        track = reader.read(audio_file)

        assert track.title == "Time"
        assert track.artist == "Pink Floyd"
        assert track.album == "The Dark Side of the Moon"
        assert track.track_number == 4
        assert track.disc_number == 1
        assert track.year == 1973
        assert track.genre == "Progressive Rock"
        assert track.duration_seconds == 425.0
        assert track.bitrate_kbps == 920
        assert track.format == MusicFormat.FLAC


def test_music_reader_filename_regex_fallback(tmp_path: Path):
    audio_file = tmp_path / "07 - Comfortably Numb.mp3"
    audio_file.write_bytes(b"dummy mp3 data")

    # When TinyTag fails or returns empty metadata
    with patch(
        "media_cron.metadata.music_reader.TinyTag.get", side_effect=Exception("Corrupt tag")
    ):
        reader = MusicMetadataReader()
        track = reader.read(audio_file)

        assert track.title == "Comfortably Numb"
        assert track.track_number == 7
        assert track.format == MusicFormat.MP3


def test_music_reader_disc_subfolder_detection(tmp_path: Path):
    disc_dir = tmp_path / "The Wall" / "CD2"
    disc_dir.mkdir(parents=True)
    audio_file = disc_dir / "01 - Hey You.flac"
    audio_file.write_bytes(b"dummy")

    with patch("media_cron.metadata.music_reader.TinyTag.get", side_effect=Exception("No tag")):
        reader = MusicMetadataReader()
        track = reader.read(audio_file)

        assert track.title == "Hey You"
        assert track.track_number == 1
        assert track.disc_number == 2
