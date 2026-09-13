# Contract: Book Converter Engine Interface

**Feature**: Book Identification, UDC Classification, and EPUB Conversion
**Branch**: `004-book-identification-conversion`
**Date**: 2026-09-09

## 1. Converter Protocol

All conversion backends implementing format transformation to EPUB MUST adhere to `BookConverterProtocol`:

```python
from typing import Protocol, runtime_checkable
from pathlib import Path
from media_cron.metadata.models import BookFormat, BookMetadata


class ConverterError(Exception):
    """Base exception for converter failures."""

    pass


class ConverterUnavailableError(ConverterError):
    """Raised when the converter binary/engine is not installed or available."""

    pass


class ConversionFailedError(ConverterError):
    """Raised when the conversion tool exits with an error or fails validation."""

    pass


class ConversionTimeoutError(ConverterError):
    """Raised when conversion exceeds configured timeout."""

    pass


@runtime_checkable
class BookConverterProtocol(Protocol):
    """Protocol for digital book conversion engines."""

    @property
    def engine_name(self) -> str:
        """Unique engine identifier (e.g. 'calibre', 'python_fallback')."""
        ...

    def is_available(self) -> bool:
        """Checks if the required runtime tools or libraries are available."""
        ...

    def supports_format(self, source_format: BookFormat) -> bool:
        """Determines if the converter can process the specified source format."""
        ...

    def convert(
        self,
        source_path: Path,
        target_path: Path,
        metadata: BookMetadata | None = None,
        timeout_seconds: int = 120,
    ) -> None:
        """Converts source_path into a standard EPUB at target_path.

        Must raise ConversionFailedError or ConversionTimeoutError on failure.
        """
        ...
```

---

## 2. Standard Converters

### 2.1 `CalibreConverter`

- **Binary dependency**: `ebook-convert`
- **Availability check**: `shutil.which("ebook-convert") is not None`
- **Supported source formats**: `MOBI`, `AZW`, `AZW3`, `PDF`, `FB2`, `TXT`, `CBZ`
- **Command template**:
  ```bash
  ebook-convert <source_path> <target_path> \
    --title "<metadata.title>" \
    --authors "<metadata.author>" \
    --series "<metadata.series_name>" \
    --series-index "<metadata.volume_number>" \
    --isbn "<metadata.isbn>"
  ```
- **Error capture**: Captures `stderr` and maps non-zero exit codes to `ConversionFailedError`.

### 2.2 `PythonFallbackConverter`

- **Binary dependency**: None (pure Python standard library)
- **Availability check**: Always `True`
- **Supported source formats**: `TXT`, `FB2`
- **Behavior**: Generates a strictly conforming minimal EPUB container (`mimetype` uncompressed, `container.xml`, `content.opf`, XHTML chapter wrappers).

---

## 3. Converter Registry

```python
class BookConverterRegistry:
    def __init__(self) -> None:
        self._engines: dict[str, type[BookConverterProtocol]] = {}

    def register(self, name: str, engine_cls: type[BookConverterProtocol]) -> None:
        self._engines[name.lower()] = engine_cls

    def get(self, name: str) -> type[BookConverterProtocol]: ...

    def get_preferred_converter(self, source_format: BookFormat) -> BookConverterProtocol:
        """Returns the highest priority available converter supporting the format."""
        ...
```
