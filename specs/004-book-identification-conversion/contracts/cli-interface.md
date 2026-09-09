# Contract: CLI Interface & Telemetry Schemas

**Feature**: Book Identification, UDC Classification, and EPUB Conversion  
**Branch**: `004-book-identification-conversion`  
**Date**: 2026-09-09  

## 1. CLI Commands & Options

### 1.1 Extended `process` Command Options

The core `media-cron process` command is extended with book options:

```bash
media-cron process [OPTIONS] [PATHS]...
```

**New Options**:
- `--books / --no-books`: Enable or disable processing of digital book files (default: enabled if book paths detected or configured).
- `--book-lookup / --no-book-lookup`: Enable automated external catalog identification (default: true).
- `--udc-lookup / --no-udc-lookup`: Enable Universal Decimal Classification lookup (default: false / opt-in).
- `--convert-epub / --no-convert-epub`: Convert non-standard book formats to EPUB (default: false / opt-in).
- `--retention [preserve|archive|replace]`: Retention policy for original files after successful EPUB conversion (default: `preserve`).
- `--archive-dir PATH`: Target directory when `--retention archive` is chosen.
- `--dry-run`: Predict identification, UDC classification, and conversion actions with zero filesystem mutation.

---

### 1.2 Diagnostic Commands

#### `test-book-identify`
Tests identification and UDC lookup on a single file or query without processing the full library.

```bash
media-cron test-book-identify [OPTIONS] FILE_OR_TITLE
```

**Options**:
- `--author TEXT`: Author name if searching by text query.
- `--udc / --no-udc`: Include UDC classification lookup (default: true).
- `--format [table|json]`: Output display format (default: `table`).

**Example JSON Output**:
```json
{
  "status": "success",
  "source_file": "Dune.mobi",
  "identified": {
    "title": "Dune",
    "author": "Frank Herbert",
    "series": "Dune Chronicles",
    "volume": "1",
    "year": 1965,
    "isbn": "9780441172719",
    "provider": "openlibrary",
    "confidence": 0.96
  },
  "udc": {
    "notation": "82-311.9",
    "description": "Literature - Fiction - Science fiction",
    "confidence": 1.0,
    "source": "summary_table"
  }
}
```

#### `test-book-convert`
Tests conversion of a single book file to EPUB without changing the library.

```bash
media-cron test-book-convert [OPTIONS] SOURCE_FILE
```

**Options**:
- `--output-dir PATH`: Where to place the converted test EPUB.
- `--engine [auto|calibre|python]`: Preferred conversion engine.
- `--dry-run`: Check conversion feasibility without creating files.

---

## 2. Telemetry Output Schema

When running with `--format json`, the execution summary includes the `books_summary` block:

```json
{
  "books_summary": {
    "total_books_scanned": 42,
    "identified_external": 38,
    "identified_local_only": 4,
    "cache_hits": 12,
    "cache_misses": 30,
    "udc_classifications_assigned": 36,
    "conversions_attempted": 8,
    "conversions_succeeded": 8,
    "conversions_failed": 0,
    "conversions_skipped_already_epub": 34,
    "retention_actions": {
      "preserved": 8,
      "archived": 0,
      "replaced": 0
    },
    "duration_seconds": 14.2
  }
}
```

---

## 3. Exit Codes

In accordance with Constitution Principle IV (Deterministic Exit Codes):

| Exit Code | Meaning | Description |
|---|---|---|
| `0` | Success | All scanned books processed successfully, dry-run simulated, or diagnostic executed cleanly |
| `1` | Configuration Error | Invalid configuration file, illegal retention policy, or missing archive directory |
| `2` | Dependency Missing | Mandatory converter engine requested explicitly (e.g. `--engine calibre`) but binary absent |
| `3` | Filesystem Error | Permission denied, unwritable target directory, or disk full |
