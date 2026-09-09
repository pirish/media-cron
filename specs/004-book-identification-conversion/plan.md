# Implementation Plan: Book Identification, UDC Classification, and EPUB Conversion

**Branch**: `004-book-identification-conversion` | **Date**: 2026-09-09 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/004-book-identification-conversion/spec.md` with explicit architectural directives:
- Automated author and work title identification for digital books using embedded metadata and external catalog services.
- Local tag and header extraction across diverse formats (EPUB, MOBI, AZW, AZW3, PDF, FB2, CBZ, TXT) with zero third-party Python runtime dependencies.
- Open Library as the default zero-configuration catalog provider with strict $\ge 85\%$ confidence threshold before overriding local tags.
- Optional Universal Decimal Classification (UDC) lookup using a hybrid model: external catalog subjects and classification hints mapped through a bundled UDC summary reference table.
- Pluggable format converter architecture prioritizing Calibre `ebook-convert` for high-fidelity conversion and falling back to pure-Python converters for text/FB2 formats when Calibre is absent.
- Strict non-destructive default retention: original files preserved alongside generated EPUBs, with configurable opt-in archive or replace policies.
- Atomic file operations (write-to-temp then atomic rename) and 100% predictive `--dry-run` simulation mode.
- Persistent file-based cache (`.media-cron-cache/book_cache.json`) with configurable TTL (default 30 days) to prevent rate limits and ensure <50ms repeat lookups.

---

## Summary

Build a digital book (e-book) processing, classification, and format standardization subsystem within `media_cron`. The architecture introduces:
1. Pure standard library header and container readers in `media_cron.metadata.book_reader` for EPUB, MOBI, AZW/AZW3, PDF, FB2, and CBZ.
2. A `BookIdentifier` that leverages the existing provider protocol and confidence scorer to verify titles, authors, and series data against Open Library.
3. A `UDCResolver` that maps catalog subjects and classification hints to standardized Universal Decimal Classification notations using a bundled `udc_summary.json` table.
4. A pluggable `BookConverterRegistry` supporting Calibre `ebook-convert` as the primary engine with a pure-Python fallback converter.
5. An `EPUBMetadataInjector` ensuring canonical metadata and UDC codes are embedded cleanly in generated or existing EPUB packages.
6. Pipeline and CLI extensions supporting `--books`, `--book-lookup`, `--udc-lookup`, `--convert-epub`, `--retention`, and diagnostic commands `test-book-identify` and `test-book-convert`.

---

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**:
- Standard Library: `zipfile`, `xml.etree.ElementTree`, `struct`, `urllib.request`, `urllib.parse`, `json`, `difflib`, `pathlib`, `dataclasses`, `enum`, `shutil`, `subprocess`
- Existing Dependencies: `typer` (CLI), `pyyaml` (configuration)
- Optional System Dependency: Calibre `ebook-convert` (runtime presence detected dynamically)

**Storage**: Local file-based JSON response cache (`.media-cron-cache/book_cache.json`) with atomic write updates.

**Testing**: `pytest`, `pytest-mock`, mock HTTP handlers, synthetic test book files.

**Target Platform**: Linux servers, containers (Docker / Podman), Kubernetes CronJobs, systemd timers.

**Project Type**: Library-first CLI application (`media_cron` package + `media-cron` CLI binary).

**Performance Goals**:
- Embedded tag extraction completes in < 50 milliseconds per file.
- External catalog lookups resolve in < 3.0 seconds under normal network conditions.
- Cached lookups resolve in < 50 milliseconds without outbound network calls.
- UDC subject mapping executes in < 10 milliseconds via in-memory lookup table.
- Conversion jobs enforce configurable subprocess timeouts (default 120 seconds).

**Constraints**:
- Zero additional third-party Python runtime dependencies (pure standard library).
- Strict confidence threshold ($\ge 85\%$) required to override local author/title tags.
- Non-destructive preservation of original source files by default.
- 100% predictive `--dry-run` simulation mode with zero filesystem mutations and zero cache pollution.
- Safe offline fallback when external services are disabled, unreachable, or rate-limited.
- Safe handling of special characters, apostrophes, and unicode in book titles and author names.

**Scale/Scope**: Collections with thousands of digital books across various formats.

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Constitutional Principle | Requirement | Compliance Strategy | Status |
|---|---|---|---|
| **I. Library-First & CLI-Driven** | Domain logic decoupled from schedulers; clean text/JSON CLI I/O | All book extraction, UDC mapping, and conversion logic encapsulated in reusable library modules under `media_cron.metadata`; exposed via standard CLI flags and dedicated diagnostic tools (`test-book-identify`, `test-book-convert`) | **PASS** |
| **II. Test-First (NON-NEGOTIABLE)** | TDD strictly enforced; unit, contract, and integration tests | Contract tests for `BookConverterProtocol` and `UDCResolverProtocol`, unit tests for readers and scorers, integration tests for full pipeline flows and dry-run safety | **PASS** |
| **III. Idempotency & Safety** | Atomic operations, dry-run safety, safe re-runs | Atomic tempfile rename for EPUB creation; non-destructive preservation default; `--dry-run` guarantees zero disk mutations; safe handling of corrupted files | **PASS** |
| **IV. Observability** | Structured logging, deterministic exit codes, clear telemetry | Structured logging at INFO/DEBUG/WARNING; deterministic exit codes (0, 1, 2, 3); machine-readable JSON telemetry in `books_summary` | **PASS** |
| **V. Container-Native** | Declarative configuration, separate state/volume mount points | Full YAML configuration under `books:`, environment variable overrides (`MEDIA_CRON_BOOKS_*`), dedicated `.media-cron-cache/` cache path | **PASS** |

---

## Project Structure

### Documentation (this feature)

```text
specs/004-book-identification-conversion/
├── spec.md              # Feature specification
├── plan.md              # Implementation plan (this file)
├── research.md          # Phase 0: Extraction, UDC mapping, converter architecture research
├── data-model.md        # Phase 1: Entity models, schemas, and state transitions
├── quickstart.md        # Phase 1: Runnable verification guide & test scenarios
├── contracts/           # Phase 1: Interface contracts
│   ├── converter-engine-interface.md   # BookConverterProtocol & Registry
│   ├── udc-classification-interface.md # UDCResolverProtocol & Summary Table
│   ├── cli-interface.md                # CLI options, diagnostics, and telemetry schemas
│   └── config-schema.md                # YAML schema & env var specifications
└── checklists/
    └── requirements.md  # Spec quality checklist
```

### Source Code (repository root)

```text
media_cron/
├── cli.py                          # Extended CLI with --books, --book-lookup, --udc-lookup, --convert-epub, --retention
├── config.py                       # Extended configuration model (BooksConfig, UDCConfig, BookConversionConfig)
├── models.py                       # Extended BatchSummary with books_summary telemetry
├── metadata/                       # Metadata, identification, classification, and conversion subsystem
│   ├── __init__.py
│   ├── base.py                     # Provider protocols, exceptions, and registries
│   ├── book_reader.py              # NEW: Format-aware metadata reader (EPUB, MOBI, AZW, PDF, FB2, CBZ)
│   ├── book_identifier.py          # NEW: BookIdentifier orchestrating local tags, catalog lookup, & caching
│   ├── udc.py                      # NEW: UDCResolver & bundled udc_summary.json loader
│   ├── data/
│   │   └── udc_summary.json        # NEW: Canonical UDC Summary mapping table
│   ├── converter.py                # NEW: BookConverterRegistry, CalibreConverter, PythonFallbackConverter
│   ├── epub_writer.py              # NEW: EPUBMetadataInjector updating OPF and container verification
│   ├── cache.py                    # MetadataCache persistence
│   └── scorer.py                   # ConfidenceScorer (pure Python difflib + token sets)
└── plugins/
    └── lookup/
        └── book.py                 # NEW: BookLookupPlugin integrating books into the media pipeline

tests/
├── contract/
│   ├── test_book_converter_contract.py # Verifies BookConverterProtocol compliance
│   └── test_udc_resolver_contract.py   # Verifies UDCResolverProtocol compliance
├── integration/
│   ├── test_book_pipeline.py           # End-to-end book identification, conversion, and retention
│   ├── test_book_caching.py            # Cache hit, TTL expiry, and offline operation
│   └── test_book_quickstart.py         # Verifies quickstart scenarios 1-4
└── unit/
    ├── test_book_reader.py             # Format parsing for EPUB, MOBI, AZW, PDF, FB2, CBZ
    ├── test_udc_resolver.py            # Subject and Dewey keyword to UDC notation mapping
    ├── test_book_identifier.py         # Confidence thresholding and local fallback
    ├── test_calibre_converter.py       # Calibre command generation and error handling
    ├── test_python_converter.py        # Pure-Python fallback conversion
    └── test_epub_writer.py             # OPF metadata injection and container validation
```

**Structure Decision**: Digital book domain logic is housed within `media_cron/metadata/`, sharing foundational caching and scoring infrastructure with audiobooks while providing specialized format readers, UDC classification resolution, and format conversion. The pipeline interacts with this subsystem via a dedicated `BookLookupPlugin` in `media_cron/plugins/lookup/book.py`.

---

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| None | All constitutional principles satisfied | N/A |
