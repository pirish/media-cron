from pathlib import Path

EBML_MAGIC = b"\x1a\x45\xdf\xa3"
FLAC_MAGIC = b"fLaC"
ZIP_MAGIC = b"PK\x03\x04"
PDF_MAGIC = b"%PDF-"


def validate_container_integrity(path: Path) -> tuple[bool, str | None]:
    """
    Validates container magic bytes and header structure before library organization.

    Returns:
        (is_valid, error_message)
    """
    path = Path(path)
    if not path.exists():
        return False, f"File does not exist: {path}"

    try:
        size = path.stat().st_size
    except OSError as e:
        return False, f"Cannot stat file: {e}"

    if size < 16:
        return False, f"File is empty or truncated ({size} bytes): {path.name}"

    ext = path.suffix.lower()

    try:
        with open(path, "rb") as f:
            header = f.read(64)
    except OSError as e:
        return False, f"Cannot read file header: {e}"

    # MKV / WebM
    if ext in (".mkv", ".webm"):
        if not header.startswith(EBML_MAGIC):
            return False, f"Invalid MKV header signature: {path.name}"

    # MP4 / M4V / MOV
    elif ext in (".mp4", ".m4v", ".mov", ".m4b"):
        if b"ftyp" not in header[:32] and b"moov" not in header[:32] and b"mdat" not in header[:32]:
            return False, f"Invalid MP4/M4V container atoms: {path.name}"

    # FLAC
    elif ext == ".flac":
        if not header.startswith(FLAC_MAGIC):
            return False, f"Invalid FLAC signature: {path.name}"

    # EPUB
    elif ext == ".epub":
        if not header.startswith(ZIP_MAGIC):
            return False, f"Invalid EPUB archive signature: {path.name}"

    # PDF
    elif ext == ".pdf":
        if not header.startswith(PDF_MAGIC):
            return False, f"Invalid PDF header: {path.name}"

    return True, None
