# Tasks: Book Identification, UDC Classification, and EPUB Conversion

**Branch**: `004-book-identification-conversion` | **Date**: 2026-09-09 | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Subsystem initialization and configuration models

- [X] T001 Create directory layout for book metadata and conversion subsystem in media_cron/metadata/data/ and tests/unit/metadata/
- [X] T002 Extend configuration models in media_cron/config.py with BooksConfig, UDCConfig, BookConversionConfig, and environment variable overrides
- [X] T003 [P] Extend BatchSummary in media_cron/models.py with books_summary telemetry and metrics fields

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core domain models, metadata cache integration, and configuration validation

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 [P] Unit test book configuration loading, defaults, and env var overrides in tests/unit/metadata/test_book_config.py
- [X] T005 [P] Define domain models (BookFormat, BookMetadata, UDCClassification, RetentionPolicy, ConversionJob, BookAsset) in media_cron/metadata/models.py
- [X] T006 [P] Unit test domain models serialization, constraints, and format detection in tests/unit/metadata/test_book_models.py
- [X] T007 [P] Extend MetadataCache key generation and entry schemas to support book queries and UDC caching in media_cron/metadata/cache.py
- [X] T008 [P] Unit test book metadata cache storage, hash generation, and TTL expiry in tests/unit/metadata/test_book_cache.py

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Automated Book and Author Identification (Priority: P1) 🎯 MVP

**Goal**: Extract embedded metadata and filename cues from digital book files (EPUB, MOBI, AZW, AZW3, PDF, FB2, CBZ, TXT), query Open Library, compute match confidence, and resolve canonical author and work title.

**Independent Test**: Ingest a digital book file with messy or stripped internal tags; verify the system queries Open Library, calculates confidence, resolves canonical author and title, and enriches the asset.

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T009 [P] [US1] Unit test format metadata reader for EPUB, MOBI, AZW, PDF, FB2, CBZ, and TXT in tests/unit/metadata/test_book_reader.py
- [X] T010 [P] [US1] Unit test book identification, confidence thresholding, and offline fallback in tests/unit/metadata/test_book_identifier.py
- [X] T011 [P] [US1] Integration test for single-file book identification and metadata enrichment in tests/integration/test_book_identification.py

### Implementation for User Story 1

- [X] T012 [US1] Implement format-aware BookMetadataReader using pure Python standard library in media_cron/metadata/book_reader.py
- [X] T013 [US1] Implement BookIdentifier service coordinating local reader extraction, cache lookup, Open Library provider query, and confidence scoring in media_cron/metadata/book_identifier.py
- [X] T014 [US1] Implement BookLookupPlugin in media_cron/plugins/lookup/book.py to discover and identify book files during pipeline runs

**Checkpoint**: Digital book identification MVP functional and testable independently

---

## Phase 4: User Story 2 - Universal Decimal Classification (UDC) Lookup (Priority: P2)

**Goal**: Resolve and attach standardized Universal Decimal Classification (UDC) notations and descriptors using a bundled summary reference table and catalog subjects.

**Independent Test**: Ingest a known fiction or science book with UDC lookup enabled; verify the system maps catalog subjects and attaches the correct UDC notation code and descriptor.

### Tests for User Story 2 ⚠️

- [X] T015 [P] [US2] Contract test for UDCResolverProtocol in tests/contract/test_udc_resolver_contract.py
- [X] T016 [P] [US2] Unit test UDC subject matching, Dewey crosswalk, and parent fallback in tests/unit/metadata/test_udc_resolver.py
- [X] T017 [P] [US2] Integration test for book identification with UDC classification enrichment in tests/integration/test_book_udc.py

### Implementation for User Story 2

- [X] T018 [US2] Create canonical UDC summary reference mapping table in media_cron/metadata/data/udc_summary.json
- [X] T019 [US2] Implement UDCResolver matching subjects and Dewey/LCC prefixes against UDC summary table in media_cron/metadata/udc.py
- [X] T020 [US2] Integrate UDCResolver into BookIdentifier in media_cron/metadata/book_identifier.py to enrich BookAsset when UDC lookup is enabled

**Checkpoint**: UDC classification lookup functional and testable independently alongside identification

---

## Phase 5: User Story 3 - Conversion of Source Formats to Standard EPUB (Priority: P3)

**Goal**: Convert non-standard book formats (MOBI, AZW, AZW3, PDF, FB2, TXT) into standard EPUB format with injected canonical metadata and atomic writing.

**Independent Test**: Provide a non-EPUB file (e.g. .mobi or .txt); invoke conversion; verify a valid .epub is generated with injected OPF metadata and original file preserved.

### Tests for User Story 3 ⚠️

- [X] T021 [P] [US3] Contract test for BookConverterProtocol in tests/contract/test_book_converter_contract.py
- [X] T022 [P] [US3] Unit test Calibre converter command generation, timeouts, and error handling in tests/unit/metadata/test_calibre_converter.py
- [X] T023 [P] [US3] Unit test pure-Python fallback converter for text/FB2 formats in tests/unit/metadata/test_python_converter.py
- [X] T024 [P] [US3] Unit test EPUB container integrity validation and OPF metadata injection in tests/unit/metadata/test_epub_writer.py
- [X] T025 [P] [US3] Integration test for format conversion to EPUB with metadata injection in tests/integration/test_book_conversion.py

### Implementation for User Story 3

- [X] T026 [US3] Implement EPUBMetadataInjector updating OPF metadata and verifying container compliance in media_cron/metadata/epub_writer.py
- [X] T027 [US3] Implement CalibreConverter wrapping ebook-convert with subprocess execution and timeout protection in media_cron/metadata/converter.py
- [X] T028 [US3] Implement PythonFallbackConverter for text/FB2 formats in media_cron/metadata/converter.py
- [X] T029 [US3] Implement BookConverterRegistry resolving the preferred available converter engine in media_cron/metadata/converter.py
- [X] T030 [US3] Integrate conversion execution with atomic tempfile replacement in BookLookupPlugin in media_cron/plugins/lookup/book.py

**Checkpoint**: Format conversion to EPUB with metadata injection functional and testable independently

---

## Phase 6: User Story 4 - Non-Destructive Operation, Dry-Run Simulation, and Retention Policy (Priority: P4)

**Goal**: Support retention policies (preserve, archive, replace), dry-run simulation mode, CLI options, and diagnostic commands.

**Independent Test**: Run pipeline with --dry-run against mixed formats; verify tool outputs planned identifications, UDC codes, and conversions without modifying any files.

### Tests for User Story 4 ⚠️

- [X] T031 [P] [US4] Unit test retention policy execution (preserve, archive, replace) and failure safety in tests/unit/metadata/test_book_retention.py
- [X] T032 [P] [US4] Integration test for CLI options, dry-run simulation, and retention policies in tests/integration/test_book_cli.py

### Implementation for User Story 4

- [X] T033 [US4] Implement retention policy handler (atomic archive move or verified replacement) in media_cron/metadata/converter.py
- [X] T034 [US4] Implement diagnostic CLI commands test-book-identify and test-book-convert in media_cron/cli.py
- [X] T035 [US4] Add CLI flags (--books, --book-lookup, --udc-lookup, --convert-epub, --retention, --archive-dir) to media_cron/cli.py
- [X] T036 [US4] Wire books_summary reporting and structured telemetry output into media_cron/pipeline.py

**Checkpoint**: Ambiguity resolution, dry-run simulation, CLI diagnostics, and retention policies fully integrated

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, validation suite, and code quality verification

- [X] T037 [P] Author documentation guide for book identification, UDC lookup, and conversion in media_cron/metadata/README.md
- [X] T038 Implement and verify end-to-end quickstart scenarios 1-4 in tests/integration/test_book_quickstart.py
- [X] T039 Run complete test suite and code quality gates via pytest and ruff check . and ruff format .

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phases 3-6)**: All depend on Foundational phase completion
  - Phase 3 (US1) delivers the baseline digital book identification MVP
  - Phase 4 (US2) builds upon US1 to add UDC classification
  - Phase 5 (US3) builds upon US1-US2 to add EPUB format conversion
  - Phase 6 (US4) finalizes retention policies, CLI flags, dry-run mode, and telemetry
- **Polish (Phase 7)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Depends on Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Depends on US1 identifier engine - Adds UDC classification enrichment
- **User Story 3 (P3)**: Depends on US1-US2 - Adds EPUB conversion and metadata injection
- **User Story 4 (P4)**: Depends on US1-US3 - Enforces retention policies, CLI, dry-run, and telemetry

### Parallel Opportunities

- **Phase 1**: T003 can run in parallel with T002
- **Phase 2**: T004, T005, T006, T007, T008 can be developed and tested in parallel
- **Phase 3 (US1)**: Test tasks T009, T010, T011 can be written in parallel before implementation
- **Phase 4 (US2)**: Test tasks T015, T016, T017 can run in parallel; mapping table T018 can be authored in parallel
- **Phase 5 (US3)**: Test tasks T021, T022, T023, T024, T025 can be written in parallel; converters T027 and T028 can be built in parallel
- **Phase 6 (US4)**: Test tasks T031 and T032 can be written in parallel

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 in parallel:
Task: "Unit test format metadata reader for EPUB, MOBI, AZW, PDF, FB2, CBZ, and TXT in tests/unit/metadata/test_book_reader.py"
Task: "Unit test book identification, confidence thresholding, and offline fallback in tests/unit/metadata/test_book_identifier.py"
Task: "Integration test for single-file book identification in tests/integration/test_book_identification.py"

# Implement reader, identifier service, and plugin in sequence:
Task: "Implement format-aware BookMetadataReader in media_cron/metadata/book_reader.py"
Task: "Implement BookIdentifier service in media_cron/metadata/book_identifier.py"
Task: "Implement BookLookupPlugin in media_cron/plugins/lookup/book.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T003)
2. Complete Phase 2: Foundational (T004-T008)
3. Complete Phase 3: User Story 1 (T009-T014)
4. **STOP and VALIDATE**: Run `pytest tests/unit/metadata/test_book_reader.py tests/unit/metadata/test_book_identifier.py tests/integration/test_book_identification.py`
5. Verify zero-configuration book identification against Open Library (MVP ready!)

### Incremental Delivery

1. Phase 1 + 2: Foundation ready (models, protocols, cache, config)
2. Phase 3 (US1): Digital book identification working end-to-end
3. Phase 4 (US2): UDC classification lookup and subject mapping enabled
4. Phase 5 (US3): Pluggable format conversion to standard EPUB with metadata injection
5. Phase 6 (US4): Safe retention policies, dry-run simulation, CLI options, and diagnostics
6. Phase 7: Quickstart end-to-end test suite and documentation verification

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- In accordance with Constitution Principle II (TDD), tests MUST be written and fail before implementation
- All file operations MUST employ atomic tempfile writing to ensure failure resilience (Constitution Principle III)
