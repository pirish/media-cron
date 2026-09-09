# Digital Book & Audiobook Metadata Subsystem

The `media_cron.metadata` subsystem provides automated book and author identification, Universal Decimal Classification (UDC) resolution, EPUB format conversion with metadata injection, multi-file chapter bundle aggregation, persistent response caching, and external catalog provider integration.

---

## Subsystem Architecture

```
media_cron/metadata/
├── __init__.py
├── base.py                     # MetadataProviderProtocol, registry, custom exceptions
├── cache.py                    # Persistent file-based cache with atomic writes & TTL
├── scorer.py                   # Pure Python difflib + token set confidence scorer
├── models.py                   # Domain models (BookFormat, BookMetadata, UDCClassification, etc.)
├── book_reader.py              # Pure-Python metadata extractor (EPUB, MOBI, AZW, FB2, CBZ, TXT)
├── book_identifier.py          # Book identification coordinator, cascade, and scoring
├── udc.py                      # Universal Decimal Classification (UDC) resolver
├── converter.py                # Pluggable EPUB converters (Calibre + Python fallback)
├── epub_writer.py              # EPUB metadata injector & container verification
├── aggregator.py               # Multi-file chapter bundle clustering for audiobooks
├── identifier.py               # Audiobook identification coordinator
├── data/
│   └── udc_summary.json        # Canonical UDC classification reference & Dewey crosswalk
└── providers/
    ├── __init__.py             # Built-in provider registration
    ├── openlibrary.py          # Open Library REST adapter (default keyless provider)
    └── audnexus.py             # Audnexus REST adapter (audiobook specialist)
```

---

## Core Capabilities

### 1. Digital Book Identification
- **Format-Aware Reader** (`BookMetadataReader`):
  Extracts embedded metadata and filename cues across EPUB (OPF XML), MOBI/AZW (PalmDOC/EXTH records), FB2 (FictionBook XML), CBZ (ComicInfo.xml), PDF, and plain text TXT.
- **Identifier Engine** (`BookIdentifier`):
  Coordinates local cues, disk cache, Open Library provider queries, and confidence thresholding.
- **Confidence Scoring & Precedence**:
  - $\ge 0.85$ Confidence: Canonical external title and author override local tags.
  - $[0.60, 0.85)$ Confidence: Local title and author are strictly preserved; missing fields (ISBN, subjects, year) are enriched.
  - $< 0.60$ or Offline: Graceful local-first fallback using embedded tags or sanitized filenames.

### 2. Universal Decimal Classification (UDC) Lookup
- **Hybrid Resolver** (`UDCResolver`):
  Maps catalog subject headings, tags, or Dewey Decimal hints to standardized UDC notation codes and categories using the bundled `udc_summary.json` table.
- **Hierarchical Depth Matching**:
  Prefers specific subclasses (e.g. `82-311.9` for Science fiction) over broader parent classes (e.g. `82-31` for general fiction).
- **Dewey Crosswalk**:
  Falls back to 3-digit Dewey prefixes (e.g., `813` -> `82-31`, `500` -> `5`) when subject keywords do not match.

### 3. Pluggable Format Conversion to Standard EPUB
- **Converter Registry** (`BookConverterRegistry`):
  Resolves the preferred available converter engine for any source format.
- **Calibre Converter** (`CalibreConverter`):
  High-fidelity conversion wrapping `ebook-convert` for MOBI, AZW, AZW3, PDF, FB2, TXT, CBZ with timeout and error handling.
- **Pure-Python Fallback Converter** (`PythonFallbackConverter`):
  Zero-dependency fallback converting TXT and FB2 files into valid standard EPUB containers.
- **EPUB Metadata Injector** (`EPUBMetadataInjector`):
  Injects canonical title, author, identifiers, series, and UDC classification into OPF packages with atomic tempfile writing.
- **Retention Policies** (`apply_retention_policy`):
  - `preserve` (default): Source files remain intact alongside generated EPUBs.
  - `archive`: Atomically moves source files to a designated archive directory after EPUB verification.
  - `replace`: Removes source files only after generated EPUB integrity is verified.

---

## Configuration Example

```yaml
books:
  enabled: true
  enable_external_lookup: true
  confidence_threshold: 0.85
  udc_lookup:
    enabled: true
    min_confidence: 0.70
  conversion:
    enabled: true
    preferred_engine: "calibre"  # or "python_fallback"
    retention_policy: "preserve" # or "archive", "replace"
    archive_dir: "/path/to/archive"
    timeout_seconds: 120
    inject_metadata: true
  cache:
    enabled: true
    ttl_seconds: 2592000 # 30 days
    cache_file: ".media-cron-cache/book_cache.json"
```

---

## Diagnostic CLI Commands

```bash
# 1. Identify book file or query with UDC resolution
media-cron test-book-identify "Dune.mobi" --udc --format json

# 2. Test conversion of a book file to EPUB
media-cron test-book-convert "Foundation.txt" --engine python --output-dir /tmp/books

# 3. Dry-run pipeline processing with books and conversion enabled
media-cron process /path/to/downloads --books --convert-epub --dry-run
```
