from pathlib import Path

from media_cron.integrity.validator import validate_container_integrity


def test_valid_mkv_header(tmp_path: Path):
    mkv_file = tmp_path / "valid.mkv"
    # MKV EBML header starts with 0x1A 0x45 0xDF 0xA3
    mkv_file.write_bytes(b"\x1a\x45\xdf\xa3" + b"\x00" * 100)
    is_valid, error = validate_container_integrity(mkv_file)
    assert is_valid is True
    assert error is None


def test_corrupt_mkv_header(tmp_path: Path):
    corrupt_file = tmp_path / "corrupt.mkv"
    corrupt_file.write_bytes(b"garbage data not an ebml header")
    is_valid, error = validate_container_integrity(corrupt_file)
    assert is_valid is False
    assert "Invalid MKV header" in error


def test_valid_mp4_header(tmp_path: Path):
    mp4_file = tmp_path / "valid.mp4"
    # MP4 ftyp box in first 16 bytes: length (4 bytes) + b'ftyp'
    mp4_file.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 100)
    is_valid, error = validate_container_integrity(mp4_file)
    assert is_valid is True
    assert error is None


def test_truncated_file(tmp_path: Path):
    empty_file = tmp_path / "empty.mkv"
    empty_file.write_bytes(b"")
    is_valid, error = validate_container_integrity(empty_file)
    assert is_valid is False
    assert "File is empty or truncated" in error
