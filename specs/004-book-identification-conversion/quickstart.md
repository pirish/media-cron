# Quickstart Validation Guide: Book Identification, UDC Classification, and EPUB Conversion

**Feature**: Book Identification, UDC Classification, and EPUB Conversion
**Branch**: `004-book-identification-conversion`
**Date**: 2026-09-09

## Overview

This guide provides step-by-step validation scenarios to verify end-to-end functionality for digital book identification, Universal Decimal Classification (UDC) lookup, and standard EPUB conversion.

---

## Prerequisites

1. Python 3.11+ environment with `media-cron` installed:
   ```bash
   pip install -e ".[dev]"
   ```
2. (Optional) Calibre `ebook-convert` utility for high-fidelity MOBI/AZW/PDF conversion:
   ```bash
   ebook-convert --version
   ```
   *Note: If Calibre is not installed, the pluggable converter gracefully tests text/FB2 formats with the Python fallback engine.*

---

## Validation Scenario 1: Automated Book & Author Identification

**Objective**: Verify that internal tags and filename cues accurately query external catalog providers (Open Library) and establish canonical metadata.

### Execution
```bash
media-cron test-book-identify "Frank Herbert - Dune.mobi" --format json
```

### Expected Outcome
- Identification resolves `title="Dune"` and `author="Frank Herbert"`.
- Provider identified as `openlibrary` with confidence $\ge 0.85$.
- Identifiers populated (ISBN `9780441172719`, Publication Year `1965`).
- Exit code: `0`.

---

## Validation Scenario 2: Universal Decimal Classification (UDC) Lookup

**Objective**: Verify that subject keywords and catalog classification data map to canonical UDC notations via the bundled summary table.

### Execution
```bash
media-cron test-book-identify "Isaac Asimov - Foundation.epub" --udc --format json
```

### Expected Outcome
- The UDC classification block contains:
  ```json
  "udc": {
    "notation": "82-311.9",
    "description": "Literature - Fiction - Science fiction",
    "confidence": 1.0,
    "source": "summary_table"
  }
  ```
- Non-blocking execution: books with unclassified topics return `udc: null` without halting the process.

---

## Validation Scenario 3: Format Conversion to Standard EPUB

**Objective**: Verify that non-EPUB files (e.g. `.mobi` or `.azw3`) are converted to valid EPUB format with injected canonical metadata and atomic writing.

### Setup Test File
```bash
mkdir -p /tmp/mc-books-test
touch "/tmp/mc-books-test/sample_book.txt"
echo "Sample Book Content Chapter 1" > "/tmp/mc-books-test/sample_book.txt"
```

### Execution
```bash
media-cron process /tmp/mc-books-test \
  --books \
  --convert-epub \
  --retention preserve \
  --format json
```

### Expected Outcome
- `/tmp/mc-books-test/sample_book.epub` is created.
- Valid EPUB structure confirmed (`zipfile` inspects `mimetype` and `META-INF/container.xml`).
- Original `/tmp/mc-books-test/sample_book.txt` is preserved in place.
- No temporary `.tmp` files left behind.

---

## Validation Scenario 4: Dry-Run Simulation & Failure Safety

**Objective**: Verify that running with `--dry-run` predicts all actions with zero filesystem mutations.

### Execution
```bash
media-cron process /tmp/mc-books-test \
  --books \
  --convert-epub \
  --retention replace \
  --dry-run \
  --format json
```

### Expected Outcome
- Telemetry output reports `conversions_attempted: 1` in dry-run mode.
- Zero source files deleted or renamed.
- Zero target files written to disk.
- Telemetry shows `dry_run: true`.
- Exit code: `0`.

---

## Automated Verification Test Suite

Run the full automated test suite for this feature:

```bash
pytest tests/unit/test_book_reader.py \
       tests/unit/test_udc_resolver.py \
       tests/unit/test_book_converter.py \
       tests/integration/test_book_pipeline.py -v
```
