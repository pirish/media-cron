# Research: Book Identification, UDC Classification, and EPUB Conversion

**Feature**: Book Identification, UDC Classification, and EPUB Conversion  
**Branch**: `004-book-identification-conversion`  
**Date**: 2026-09-09  

## Executive Summary

This document consolidates architectural and technical research for introducing digital book (e-book) identification, Universal Decimal Classification (UDC) resolution, and format conversion to EPUB within `media_cron`. The design adheres to the Media-Cron Constitution: library-first architecture, zero external Python runtime dependencies for core workflows, container-native isolation, non-destructive defaults, and deterministic observability.

---

## 1. E-Book Format Metadata Extraction

### Context & Challenge
Digital books exist in diverse container formats: EPUB (`.epub`), MOBI (`.mobi`), Kindle formats (`.azw`, `.azw3`), PDF (`.pdf`), FictionBook (`.fb2`), Comic Book Archives (`.cbz`, `.cbr`), and plain text (`.txt`). Extracting title, author, series, and publication identifiers (ISBN/ASIN) locally must be fast, resilient to corrupted headers, and avoid adding heavy binary dependencies to standard Python runtimes.

### Research & Findings
1. **EPUB (`.epub`)**:
   - Structure: ZIP container with `META-INF/container.xml` pointing to the Open Packaging Format (OPF) XML document (`content.opf` or `package.opf`).
   - Tags: XML namespace `http://purl.org/dc/elements/1.1/` defines `<dc:title>`, `<dc:creator>`, `<dc:identifier>`, `<dc:date>`, `<dc:subject>`, and `<meta name="calibre:series">`.
   - Parsing: Native Python `zipfile` and `xml.etree.ElementTree` extract all metadata with zero external packages.
2. **MOBI / AZW / AZW3 (`.mobi`, `.azw`, `.azw3`)**:
   - Structure: Palm Database format (PDB). Record 0 contains the PalmDOC and MOBI header. The EXTH header inside record 0 contains tag-length-value (TLV) attributes:
     - EXTH 100: Author (`creator`)
     - EXTH 104: ISBN
     - EXTH 105: Subject
     - EXTH 106: Publication date
     - EXTH 503: Updated title
   - Parsing: Standard `struct.unpack` reads PDB record offsets and EXTH blocks in fewer than 100 lines of pure Python.
3. **PDF (`.pdf`)**:
   - Structure: PDF trailer contains an `/Info` dictionary reference (`/Title`, `/Author`, `/CreationDate`). Many modern PDFs also embed an XMP metadata stream (`<x:xmpmeta>`).
   - Parsing: Binary stream scan for `/Title (...)` and `/Author (...)` in the Info dictionary or XMP chunk extracts metadata quickly without requiring heavyweight PDF rendering engines.
4. **FictionBook (`.fb2`)**:
   - Structure: Pure XML document with `<FictionBook><description><title-info>`.
   - Tags: `<book-title>`, `<author><first-name>`, `<last-name>`, `<genre>`.
   - Parsing: Standard `xml.etree.ElementTree`.
5. **Comic Book Archive (`.cbz`)**:
   - Structure: ZIP container containing images and optional `ComicInfo.xml`.
   - Parsing: Standard `zipfile` and XML parsing.

### Decision
Implement `BookMetadataReader` in `media_cron.metadata.book_reader` using pure Python standard library modules (`zipfile`, `xml.etree.ElementTree`, `struct`). Fall back to filename tokenization (`parse_filename`) when embedded metadata is missing or corrupted.

### Alternatives Considered
- *Using `ebooklib`*: Heavyweight third-party dependency; only supports EPUB, does not handle MOBI, AZW, or PDF.
- *Requiring `mutagen` or `exiftool`*: Additional runtime or system dependencies that violate Constitution Principle V (container simplicity) when pure standard library stream extraction suffices.

---

## 2. Universal Decimal Classification (UDC) Lookup & Mapping

### Context & Challenge
The user explicitly requested Universal Decimal Classification (UDC) lookup as an available option. UDC is an internationally standardized, language-independent library classification system covering all fields of knowledge via decimal notations:
- `0`: Science and Knowledge, Organization, Computer Science, Information
- `1`: Philosophy, Psychology
- `2`: Religion, Theology
- `3`: Social Sciences, Economics, Law
- `5`: Mathematics, Natural Sciences
- `6`: Applied Sciences, Medicine, Technology
- `7`: The Arts, Architecture, Music, Sport
- `8`: Language, Linguistics, Literature (e.g., `82-31` Fiction/Novels, `82-311.9` Science Fiction, `82-32` Short Stories, `82-93` Children's Literature)
- `9`: Geography, Biography, History

Most public book APIs (such as Open Library, Google Books, Crossref) provide subject keywords (e.g., "Fiction", "Science Fiction", "History", "Physics") and occasionally Dewey Decimal Classification (DDC) or Library of Congress Classification (LCC) codes, but do not provide raw UDC codes directly for every book.

### Research & Findings
1. **DDC-to-UDC Alignment**: Both Dewey Decimal Classification and UDC share common decimal roots. Top-level classes correspond directly (DDC 800s → UDC 8; DDC 500s → UDC 5).
2. **Subject-to-UDC Mapping**: The International Federation for Information and Documentation (FID) and the UDC Consortium publish the UDC Summary (UDCS) covering over 2,000 standard headings.
3. **Zero-Subscription Operational Model**: Querying proprietary classification web APIs requires API keys, rate limits, and network dependency. Bundling a canonical UDC Summary lookup table in JSON format (`udc_summary.json`) enables instant, deterministic, zero-network resolution from extracted subjects and classification codes.

### Decision
Adopt a **hybrid UDC resolution strategy**:
1. When UDC lookup is enabled, retrieve work subjects and catalog classification hints from Open Library or candidate metadata.
2. Pass normalized subjects and Dewey/LCC prefixes through a bundled `UDCResolver` that matches candidate keywords against `udc_summary.json` (hierarchical prefix scoring).
3. If an exact subject match exists (e.g. "Science Fiction"), assign the specific notation (`82-311.9`). If broad, assign the parent category (`82-31` or `82`). If no match, gracefully mark unclassified without interrupting processing.
4. Cache UDC resolutions in the persistent metadata cache.

### Alternatives Considered
- *Direct HTTP queries to external UDC API*: External UDC web services have strict rate limits and require authentication keys, introducing network failure points during unattended cron runs.
- *Local-only keyword matching without catalog subjects*: Misses rich subject classifications provided by Open Library when local file tags are sparse.

---

## 3. Pluggable E-Book Conversion Engine

### Context & Challenge
The system must support converting non-standard book formats (MOBI, AZW, AZW3, PDF, FB2, TXT) into standard EPUB format. Digital book conversions range from simple text re-wrapping to complex CSS typography and reflow adjustments.

### Research & Findings
1. **Calibre `ebook-convert`**:
   - Industry-standard conversion engine available as a standard CLI tool on Linux (`calibre` package).
   - Handles MOBI, AZW, AZW3, FB2, PDF, DOCX, TXT with highest formatting fidelity, automatic table of contents generation, and EPUB 3 compliance.
   - Command signature: `ebook-convert <input> <output.epub> [options]`.
   - Execution time: typically 1–5 seconds for standard books.
2. **Pure-Python Fallback Converter**:
   - For environments where Calibre cannot be installed (minimal container images, restricted environments), text-based formats (`.txt`, `.fb2`, `.html`) can be packaged into standard EPUB containers using Python's `zipfile` and standard EPUB structural templates (`mimetype`, `container.xml`, `content.opf`, `toc.ncx`).
3. **Pluggable Architecture**:
   - Defining a `BookConverterProtocol` allows the system to detect available converters dynamically at startup.
   - The primary `CalibreConverter` checks `shutil.which("ebook-convert")`. If available, it handles all supported formats.
   - If Calibre is absent, the `PythonFallbackConverter` handles supported text/markup formats while logging clear, non-fatal diagnostics for binary formats requiring Calibre.

### Decision
Implement a pluggable `BookConverterRegistry` and `BookConverterProtocol` in `media_cron.metadata.converter`:
- `CalibreConverter`: Primary converter wrapping `ebook-convert` with subprocess timeout guards, clean exit code validation, and error stream capture.
- `PythonFallbackConverter`: Built-in fallback converter for text/FB2 formats when Calibre is not present.
- Configurable conversion timeout (default 120 seconds per book) to prevent runaway processes on pathological files.

### Alternatives Considered
- *Requiring Calibre as a mandatory hard dependency*: Would break Media-Cron in minimal container images or systems without Calibre installed.
- *Pure-Python only without Calibre*: Cannot reliably decompress and re-flow proprietary AZW/AZW3 or binary MOBI formatting without porting massive Calibre conversion codebases.

---

## 4. EPUB Metadata Injection & Validation

### Context & Challenge
When a book is converted to EPUB or an existing EPUB is processed, the system must inject canonical metadata (title, author, publisher, date, identifiers, and UDC notation) into the EPUB container without corrupting the file or violating EPUB specification standards.

### Research & Findings
1. **EPUB Container Rules**:
   - File is a standard ZIP archive.
   - First entry MUST be `mimetype` with uncompressed storage (`ZIP_STORED`), containing the exact ASCII string `application/epub+zip`.
   - `META-INF/container.xml` specifies the relative path to the `.opf` file.
   - The `.opf` package document defines metadata inside `<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">`.
2. **Injecting UDC into EPUB**:
   - Dublin Core `<dc:subject>` accommodates classification terms: `<dc:subject>UDC: 82-311.9 (Science Fiction)</dc:subject>`.
   - Modern EPUB 3 allows `<meta property="dcterms:subject">UDC 82-311.9</meta>`.
3. **Validation**:
   - Checking for the uncompressed `mimetype` header and valid OPF XML confirms container integrity before finalizing conversion.

### Decision
Implement `EPUBMetadataInjector` in `media_cron.metadata.epub_writer`. It inspects existing EPUBs or post-conversion output, updates the OPF metadata block with canonical title, author, and UDC classification, and rewrites the ZIP container ensuring strict compliance with EPUB packaging requirements.

---

## 5. Non-Destructive Filesystem Operations & Retention

### Context & Challenge
Constitution Principle III mandates idempotency and failure resilience: non-destructive execution must be the default, operations modifying files must provide verified dry-run mode, and partial failures must not leave corrupt state.

### Research & Findings
1. **Atomic Write Pattern**:
   - Write new EPUB file to temporary path: `<target_dir>/<filename>.epub.tmp.<uuid>`.
   - Validate output file size > 0 and verify ZIP/EPUB container integrity.
   - Atomically rename via `os.replace` to target `<filename>.epub`.
2. **Original File Retention Options**:
   - `PRESERVE` (default): Source file (e.g. `Book.mobi`) remains in place; new `Book.epub` is generated alongside it.
   - `ARCHIVE`: Source file is atomically moved to an archive folder (e.g. `_archive/` or configured directory) after target EPUB passes validation.
   - `REPLACE`: Source file is deleted only after target EPUB passes validation.
3. **Dry-Run Predictability**:
   - `--dry-run` performs local extraction, external catalog lookup, UDC resolution, and reports planned conversions and retention actions with zero filesystem mutations.

### Decision
Enforce atomic writes with tempfile replacement and support the three retention policies (`preserve`, `archive`, `replace`) with `preserve` as the strict non-destructive default.
