# Feature Specification: Book Identification, UDC Classification, and EPUB Conversion

**Feature Branch**: `004-book-identification-conversion`

**Created**: 2026-09-09

**Status**: Draft

**Input**: User description: "books:  Best efforts should be made to identify the work being processed as well as the author, automatically.  Option for universal decimal system lookup should be available as well. Options to convert into standard format should be supported (epub)"

## Clarifications

### Session 2026-09-09
- Q: What conversion engine strategy should the system use to convert non-standard book formats into EPUB? → A: Pluggable converter supporting Calibre `ebook-convert` as primary with pure-Python fallback.
- Q: What should be the default lifecycle policy for the original non-EPUB file after a successful EPUB conversion? → A: Preserve original files alongside generated EPUBs by default, with opt-in flags for archiving or replacement.
- Q: Where should the system source Universal Decimal Classification (UDC) notations when UDC lookup is enabled? → A: Hybrid lookup mapping external catalog subjects and classification codes to UDC via bundled summary tables.
- Q: How should multi-file or multi-volume book publications be handled during identification and conversion? → A: Treat each file as an independent book entity, capturing series and volume number metadata.
- Q: When external book metadata conflicts with embedded tags, under what conditions should external metadata override local tags? → A: High confidence (≥85%) required to override local author/title; otherwise retain local tags and only populate missing fields.


## User Scenarios & Testing *(mandatory)*

### User Story 1 - Automated Book and Author Identification (Priority: P1)

A digital library user places electronic book files (such as `.epub`, `.mobi`, `.azw`, `.azw3`, `.pdf`, `.fb2`, or `.cbz`) into an incoming staging directory or runs an ingestion scan. The system inspects internal document metadata and filename patterns, automatically queries configured external catalog sources to identify and disambiguate the work title and author name, computes a match confidence score, and normalizes the book's metadata record.

**Why this priority**: Accurate identification of author and work title is the foundational prerequisite for all digital book cataloging, library organization, classification, and format conversion. Delivering zero-configuration author and title resolution provides an immediate, independently testable MVP.

**Independent Test**: Provide an e-book file with partial, messy, or stripped internal tags but a recognizable filename (or vice versa); run the identification process; verify that the system accurately identifies the canonical author and work title without manual user intervention.

**Acceptance Scenarios**:

1. **Given** a digital book file containing embedded metadata tags, **When** processed by the identification engine, **Then** the system extracts the title, author, and available identifiers, queries external catalog providers, and establishes canonical metadata.
2. **Given** a digital book file with missing or stripped internal metadata and an unstructured filename (e.g., `Author - Title.mobi`), **When** scanned, **Then** the system uses filename heuristic tokenization to query external book catalogs and resolves the correct author and work title.
3. **Given** external lookup services are offline, rate-limited, or disabled, **When** a book file is processed, **Then** the system falls back gracefully to local embedded tags and filename heuristics without failure or terminating the pipeline.

---

### User Story 2 - Universal Decimal Classification (UDC) Lookup (Priority: P2)

A library user or curator with classification enabled processes books and wants them classified according to the Universal Decimal Classification (UDC) system (e.g., assigning UDC notations like `82-31` for fiction/novels, `51` for mathematics, etc.). When the UDC lookup option is active, the system consults catalog subject headings, external classification databases, or UDC summary tables to resolve the appropriate UDC classification code and human-readable descriptor for the identified work, enriching the book's metadata record.

**Why this priority**: Universal Decimal Classification enables standardized library categorization, shelf organization, and systematic filtering across multi-language collections, fulfilling the explicit user requirement for universal decimal system lookup while remaining an optional, non-blocking enrichment.

**Independent Test**: Ingest a known fiction or non-fiction book with UDC lookup enabled; verify the system queries classification data and attaches the correct UDC notation code and classification category to the book's metadata record.

**Acceptance Scenarios**:

1. **Given** a book identified by title and author with UDC lookup enabled, **When** catalog metadata is retrieved, **Then** the system queries classification data to map subjects to a UDC notation and classification label.
2. **Given** a book where no exact or specific UDC notation is found in external records, **When** UDC lookup is executed, **Then** the system assigns a broad top-level UDC class based on subject keywords or safely marks UDC classification as unassigned without interrupting processing.
3. **Given** UDC lookup is disabled via configuration or CLI flag, **When** books are processed, **Then** the system bypasses UDC queries entirely and proceeds with standard identification and processing.

---

### User Story 3 - Conversion of Source Formats to Standard EPUB (Priority: P3)

A reader with a diverse collection of digital book formats (such as MOBI, AZW, AZW3, PDF, FB2, or TXT) wants standard EPUB files for broad compatibility with e-readers and media servers. With format conversion enabled, the system converts non-EPUB book files into valid standard EPUB format, injects the identified canonical metadata (title, author, identifiers, and UDC classification if available) into the generated EPUB, and writes the output atomically.

**Why this priority**: Standardizing on EPUB ensures long-term readability, reflowable typography, and interoperability across open-source e-readers and modern media management platforms.

**Independent Test**: Provide a non-EPUB format file (e.g., `.mobi` or `.azw3`); invoke the conversion option; verify a valid `.epub` file is generated containing the identified author, title, and metadata, leaving the original file intact (or handling according to configured retention policy).

**Acceptance Scenarios**:

1. **Given** an existing non-EPUB book file (e.g. `.mobi` or `.azw3`) and conversion enabled, **When** the processing pipeline runs, **Then** the system converts the document to a standard `.epub` file containing updated metadata with canonical author and title.
2. **Given** an incoming file that is already in standard `.epub` format, **When** processed with conversion enabled, **Then** the system recognizes it is already in standard format, skips redundant re-conversion, and only updates or injects metadata if needed.
3. **Given** conversion fails due to DRM encryption, unsupported proprietary structure, or file corruption, **When** conversion is attempted, **Then** the system logs a structured warning, leaves the original file untouched, and reports the failure without halting the remaining batch.

---

### User Story 4 - Non-Destructive Operation, Dry-Run Simulation, and Retention Policy (Priority: P4)

An operator running automated cron jobs or inspecting changes locally needs guarantees that book identification, UDC lookup, and format conversion are safe and transparent. The system supports dry-run mode (reporting proposed identifications, UDC codes, and planned conversions without modifying any files) and provides a configurable original-file retention policy (defaulting to non-destructive preservation of original source files alongside generated EPUBs, with options to archive or replace).

**Why this priority**: In unattended cron and automation environments, data preservation and idempotency are strictly mandated. Operators must be able to simulate pipeline runs safely and verify actions before modifying filesystem state.

**Independent Test**: Run the command with `--dry-run` against a directory of mixed book formats; verify the tool outputs planned metadata enrichments, classification codes, and conversion actions without modifying source files or writing new files to disk.

**Acceptance Scenarios**:

1. **Given** a directory of books processed with `--dry-run`, **When** executed, **Then** the system outputs a detailed plan of identified titles, authors, UDC classifications, and planned EPUB conversions without creating, modifying, or deleting any files.
2. **Given** default conversion settings, **When** a source book is converted to EPUB, **Then** the original source file is preserved intact alongside the new EPUB file.
3. **Given** a retention policy explicitly set to archive or replace, **When** conversion completes successfully and integrity is verified, **Then** the original file is moved to the archive destination or removed, ensuring failed conversions never delete source files.

---

### Edge Cases

- **DRM-Protected Files**: E-books with proprietary digital rights management (DRM) cannot be parsed or converted; the system must detect DRM protection, log an informative non-fatal warning, preserve the original file, and continue processing remaining items.
- **Image-Heavy or Complex Fixed-Layout Documents**: Converting complex PDFs to EPUB can yield suboptimal formatting or high memory usage; the system must enforce conversion timeouts and resource limits.
- **Multiple Authors, Editors, or Anthologies**: Books with multiple contributing authors, translators, or editors (e.g., "Edited by...", "Author A and Author B"); the system must parse and preserve primary author and co-author/contributor roles without dropping collaborators.
- **External Catalog Outages or Rate Limits**: External lookup APIs (catalog providers, UDC classification services) may experience downtime, connection timeouts, or rate limits (HTTP 429); the system must employ local-first fallback, persistent caching, and configurable timeouts to prevent pipeline stalling.
- **Generic or Ambiguous Titles**: Works titled "Selected Works", "Essays", or common single-word titles; strict confidence scoring (author + title correlation ≥85%) must prevent false-positive external metadata overrides.
- **Corrupted or Truncated Files**: Truncated ZIP containers in EPUB/CBZ or corrupt file headers; the system must validate container integrity before attempting reading or conversion.
- **Pre-existing Target Files**: If an EPUB with the same target name already exists, the system must verify whether it has already been processed (idempotency) and avoid duplicate work or accidental overwriting unless force execution is specified.
- **Partial or Interrupted Conversions**: Converter process aborts or crashes mid-way; temporary files must be cleaned up and atomic file rename used so no corrupted or half-written EPUB is left in place.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST extract author, title, series name, volume/part number, publication date, and identifiers (ISBN, ASIN, UUID) from embedded metadata of standard digital book formats (including EPUB, MOBI, AZW, AZW3, PDF, FB2, and comic book archives CBZ/CBR) and filename/directory patterns, treating each digital book file as an independent book asset.
- **FR-002**: System MUST automatically query configured external catalog providers (such as Open Library) to identify and verify the canonical work title and author name for processed books.
- **FR-003**: System MUST compute a confidence score for candidate book matches and require a strict confidence threshold (≥85%) before external metadata can override existing local author and title tags; below 85% confidence, system MUST preserve local tags and only use external metadata to populate missing fields (e.g. ISBN, publisher, publication date, or UDC notation).
- **FR-004**: System MUST provide a local-only mode that bypasses all network queries and relies solely on embedded file metadata and filename heuristics.
- **FR-005**: System MUST provide an optional Universal Decimal Classification (UDC) lookup capability, configurable via settings or CLI options.
- **FR-006**: When UDC lookup is enabled, system MUST query external catalog subjects and classification data (such as Open Library subjects or Dewey/LCC fields) and map them to a canonical UDC notation code and descriptor using a bundled UDC summary reference table.
- **FR-007**: If UDC lookup is unable to find an exact classification for a book, system MUST gracefully fall back to a higher-level general classification class or mark UDC classification as unassigned without interrupting processing.
- **FR-008**: System MUST support converting non-EPUB book formats (including MOBI, AZW, AZW3, PDF, FB2, TXT) into standard EPUB format when conversion is requested, utilizing a pluggable conversion architecture that prioritizes Calibre `ebook-convert` and falls back to pure-Python conversion libraries when external binaries are not installed.
- **FR-009**: System MUST inject canonical metadata (title, author, publication date, identifiers, and UDC code if available) into converted and processed EPUB files.
- **FR-010**: System MUST recognize files that are already in standard EPUB format and avoid redundant re-conversion.
- **FR-011**: System MUST perform all format conversions using atomic write operations (writing to a temporary file and renaming upon verification) to prevent partial or corrupted files.
- **FR-012**: System MUST preserve original non-EPUB source files alongside generated EPUB files by default, while supporting configurable user options to either move originals to a designated archive folder or delete them only after the generated EPUB passes integrity checks.
- **FR-013**: System MUST support dry-run simulation mode (`--dry-run`), reporting identified titles, authors, UDC classifications, and planned conversions without mutating files on disk.
- **FR-014**: System MUST cache external metadata queries and UDC classification lookups in a local persistent cache with a configurable TTL (defaulting to 30 days) to minimize external network requests.
- **FR-015**: System MUST enforce configurable timeouts and failure handling on external API requests and format conversion operations to ensure pipeline resilience during unattended execution.
- **FR-016**: System MUST emit structured logging and machine-readable output detailing identification confidence, UDC codes, conversion status, and processing duration.

### Key Entities *(include if feature involves data)*

- **BookAsset**: Represents an e-book file or publication, containing file path, format, file size, embedded metadata (title, author, series name, volume number, publisher, publication date, ISBN/identifiers), canonical metadata, UDC notation, and processing state.
- **AuthorRecord**: Represents author information including canonical name, role (author, editor, illustrator, translator), and optional identifier.
- **UDCClassification**: Represents a Universal Decimal Classification entry, containing notation code (e.g. `82-31`), human-readable category description, confidence level, and source.
- **ConversionJob**: Represents a format conversion task, containing source path, source format, target format (EPUB), temporary output path, final output path, conversion options, and status (pending, completed, skipped, failed).
- **MetadataMatch**: Represents a metadata match candidate evaluated by the identification engine, containing matched title, author, identifiers, provider name, and confidence score.
- **BookMetadataCache**: Persistent cache storing external book queries and UDC lookups to accelerate repeated runs and operate within rate limits.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: At least 95% of digital books with standard embedded tags or standard naming conventions (`Author - Title`) are accurately identified with canonical title and author without manual intervention.
- **SC-002**: When UDC lookup is enabled, at least 90% of successfully identified non-fiction and standard fiction works in supported catalogs receive a valid UDC notation.
- **SC-003**: 100% of non-DRM, uncorrupted convertible source files (MOBI, AZW, AZW3, FB2, TXT) convert into valid EPUB files that conform to EPUB specification standards and retain canonical metadata.
- **SC-004**: Zero source files deleted or corrupted on conversion failure; failed conversions leave the original file completely intact in 100% of test cases.
- **SC-005**: Repeated metadata lookups for cached book assets resolve in under 50 milliseconds from the local persistent cache.
- **SC-006**: Dry-run mode produces 100% accurate predictions of identification, UDC classification, and conversion actions with zero filesystem modifications.
- **SC-007**: 100% of network interruptions or external service errors degrade gracefully to local metadata without crashing or generating unhandled exceptions.

## Assumptions

- **Standard format target**: The standard format requested is EPUB (EPUB 3 / EPUB 2 backward compatible).
- **Default non-destructive preservation**: Converted EPUBs are placed alongside or in designated output paths while preserving the original source file by default, in alignment with Constitution Principle III (Idempotency & Failure Resilience).
- **UDC lookup as optional enrichment**: UDC lookup is an opt-in capability that operates via a hybrid strategy, extracting subject headings and classification hints from catalog records and mapping them through bundled UDC summary reference tables.
- **Precedence order**: High-confidence external matches (≥85% match confidence) take precedence to normalize and standardize title, author, and secondary metadata, while local tags take precedence over lower-confidence or ambiguous external results.
- **Conversion tooling**: Format conversion employs a pluggable architecture utilizing Calibre `ebook-convert` as the primary high-fidelity engine and falling back to pure-Python conversion libraries when external binaries are absent.
- **Local-first fallback**: System remains fully operational without internet connectivity, utilizing local file tags and filename heuristics.
- **Persistent caching**: Metadata and classification query results are stored in the local cache directory with a 30-day default TTL.
