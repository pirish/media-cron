import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from media_cron.metadata.converter import (
    CalibreConverter,
    ConversionFailedError,
    ConversionTimeoutError,
    ConverterUnavailableError,
)
from media_cron.metadata.models import BookMetadata


def test_calibre_converter_command_generation():
    converter = CalibreConverter()
    source = Path("/tmp/book.mobi")
    target = Path("/tmp/book.epub")
    metadata = BookMetadata(
        title="Dune",
        author="Frank Herbert",
        series_name="Dune Chronicles",
        volume_number="1",
        isbn="9780441172719",
    )

    cmd = converter._build_command(source, target, metadata)
    assert cmd[0] == "ebook-convert"
    assert str(source) in cmd
    assert str(target) in cmd
    assert "--title" in cmd
    assert "Dune" in cmd
    assert "--authors" in cmd
    assert "Frank Herbert" in cmd
    assert "--series" in cmd
    assert "Dune Chronicles" in cmd
    assert "--series-index" in cmd
    assert "1" in cmd
    assert "--isbn" in cmd
    assert "9780441172719" in cmd


def test_calibre_converter_success(tmp_path: Path):
    converter = CalibreConverter()
    source = tmp_path / "book.mobi"
    source.write_bytes(b"dummy mobi content")
    target = tmp_path / "book.epub"

    def fake_run(cmd, **kwargs):
        # Write dummy output file to simulate calibre creating target
        temp_out = Path(cmd[2])
        temp_out.write_bytes(b"converted epub")
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="Success", stderr="")

    with patch("shutil.which", return_value="/usr/bin/ebook-convert"):
        with patch("subprocess.run", side_effect=fake_run) as mock_run:
            converter.convert(source, target)
            mock_run.assert_called_once()
            assert target.exists()
            assert target.read_bytes() == b"converted epub"


def test_calibre_converter_unavailable():
    converter = CalibreConverter()
    with patch("shutil.which", return_value=None):
        assert not converter.is_available()
        with pytest.raises(ConverterUnavailableError):
            converter.convert(Path("/tmp/book.mobi"), Path("/tmp/book.epub"))


def test_calibre_converter_failure():
    converter = CalibreConverter()
    with patch("shutil.which", return_value="/usr/bin/ebook-convert"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["ebook-convert"], returncode=1, stdout="", stderr="Error converting file"
            )
            with pytest.raises(ConversionFailedError, match="Error converting file"):
                converter.convert(Path("/tmp/book.mobi"), Path("/tmp/book.epub"))


def test_calibre_converter_timeout():
    converter = CalibreConverter()
    with patch("shutil.which", return_value="/usr/bin/ebook-convert"):
        with patch(
            "subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="ebook-convert", timeout=10)
        ):
            with pytest.raises(ConversionTimeoutError):
                converter.convert(
                    Path("/tmp/book.mobi"), Path("/tmp/book.epub"), timeout_seconds=10
                )
