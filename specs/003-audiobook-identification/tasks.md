# Tasks: Audiobook Identification and Author Disambiguation

**Branch**: `003-audiobook-identification` | **Date**: 2026-09-08 | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Subsystem initialization and configuration models

- [X] T001 Create directory layout for metadata subsystem in media_cron/metadata/ and media_cron/metadata/providers/ and tests/unit/metadata/
- [X] T002 Extend configuration models in media_cron/config.py with AudiobookConfig, ExternalProviderConfig, MetadataCacheConfig, and environment variable overrides
- [X] T003 [P] Extend MediaAsset and BatchSummary in media_cron/models.py with audiobook fields (narrator, series, volume, confidence, identification_source, and audiobook_summary)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core domain abstractions, scoring heuristic, and persistent caching engine

- [X] T004 [P] Unit test configuration loading, defaults, and env var overrides in tests/unit/metadata/test_config.py
- [X] T005 [P] Define domain models (MetadataMatch, AudiobookBundle, MetadataCacheEntry) in media_cron/metadata/models.py
- [X] T006 [P] Implement MetadataProviderProtocol, MetadataProviderRegistry, and custom exceptions in media_cron/metadata/base.py
- [X] T007 [P] Implement ConfidenceScorer with pure Python difflib token scoring, 85% thresholding, and mismatch penalty in media_cron/metadata/scorer.py
- [X] T008 [P] Unit test ConfidenceScorer in tests/unit/metadata/test_confidence_scorer.py
- [X] T009 [P] Implement MetadataCache with atomic disk persistence, SHA-256 keys, and TTL evaluation in media_cron/metadata/cache.py
- [X] T010 [P] Unit test MetadataCache in tests/unit/metadata/test_metadata_cache.py

**Checkpoint**: Core domain, scoring engine, and cache foundation ready - user stories can now begin

---

## Phase 3: User Story 1 - Automated Local & External Identification for Single-File Audiobooks (Priority: P1) 🎯 MVP

**Goal**: Ingest single-file audiobooks (.m4b, .mp3), extract local tags and filename cues, query primary provider (Open Library), and standardize author and work title.

**Independent Test**: Ingest a standalone .m4b with messy tags; verify the system queries Open Library, standardizes author and work title, and enriches the asset without human intervention.

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T011 [P] [US1] Contract test for MetadataProviderProtocol with mock provider in tests/contract/test_metadata_provider_contract.py
- [X] T012 [P] [US1] Unit test OpenLibraryProvider URL building, timeout handling, and JSON parsing in tests/unit/metadata/test_openlibrary_provider.py
- [X] T015 [P] [US1] Unit test audiobook identification and fallback heuristics in tests/unit/metadata/test_audiobook_lookup.py
- [X] T018 [P] [US1] Integration test for single-file audiobook ingestion and enrichment in tests/integration/test_audiobook_single_file.py

### Implementation for User Story 1

- [X] T013 [US1] Implement OpenLibraryProvider using pure Python urllib.request in media_cron/metadata/providers/openlibrary.py
- [X] T014 [US1] Register OpenLibraryProvider in MetadataProviderRegistry within media_cron/metadata/providers/__init__.py
- [X] T016 [US1] Implement AudiobookIdentifier service coordinating local tag extraction, cache check, provider lookup, and confidence scoring in media_cron/metadata/identifier.py
- [X] T017 [US1] Update AudioTagLookup in media_cron/plugins/lookup/audio.py to integrate AudiobookIdentifier for .m4b and audiobook-classified media

**Checkpoint**: Single-file audiobook identification MVP functional and testable independently

---

## Phase 4: User Story 2 - Multi-File Audiobook Bundle Identification (Priority: P2)

**Goal**: Aggregate chapter/disc tracks in folders (Author - Title/Track 01.mp3, CD1/, CD2/) into a single AudiobookBundle work.

**Independent Test**: Provide a folder containing chapter .mp3 files across CD1/ and CD2/ subdirectories with identical album tags; verify the system outputs a single coherent audiobook identification with shared author and title.

### Tests for User Story 2 ⚠️

- [X] T019 [P] [US2] Unit test multi-file bundle clustering, disc subfolder traversal, and album tag consensus in tests/unit/metadata/test_audiobook_bundle.py
- [X] T022 [P] [US2] Integration test multi-file chapter bundle identification and organization in tests/integration/test_audiobook_multi_file.py

### Implementation for User Story 2

- [X] T020 [US2] Implement AudiobookBundleAggregator clustering multi-track directories and disc subfolders in media_cron/metadata/aggregator.py
- [X] T021 [US2] Integrate AudiobookBundleAggregator into AudioTagLookup in media_cron/plugins/lookup/audio.py so bundles receive unified work metadata across all chapter files

**Checkpoint**: Multi-file chapter bundles and single-file audiobooks both functional and testable independently

---

## Phase 5: User Story 3 - Configurable External Metadata Services & Cascade Priority (Priority: P3)

**Goal**: Enable configuring multiple providers (Open Library + Audnexus) with priority order, custom endpoints, timeouts, and rate limits.

**Independent Test**: Configure Open Library and Audnexus in priority order; verify that the system queries Open Library first and only falls back to Audnexus if no confident match is returned.

### Tests for User Story 3 ⚠️

- [X] T023 [P] [US3] Unit test AudnexusProvider URL generation, timeout handling, and JSON parsing in tests/unit/metadata/test_audnexus_provider.py
- [X] T026 [P] [US3] Unit test provider cascade sequencing and priority fallback in tests/unit/metadata/test_provider_cascade.py
- [X] T028 [P] [US3] Integration test multi-provider cascade order and rate-limit delays in tests/integration/test_provider_cascade.py

### Implementation for User Story 3

- [X] T024 [US3] Implement AudnexusProvider querying Audnexus book API via urllib.request in media_cron/metadata/providers/audnexus.py
- [X] T025 [US3] Register AudnexusProvider in MetadataProviderRegistry within media_cron/metadata/providers/__init__.py
- [X] T027 [US3] Implement sequential provider cascade querying with timeout and rate-limit enforcement in AudiobookIdentifier in media_cron/metadata/identifier.py

**Checkpoint**: Multi-provider cascade and custom provider configurations functional

---

## Phase 6: User Story 4 - Ambiguity Resolution, Confidence Reporting & Cache Integration (Priority: P4)

**Goal**: Enforce strict 85% confidence threshold for external overrides, record telemetry, support CLI flags and diagnostics.

**Independent Test**: Run identification on an audiobook with ambiguous title; verify system preserves local author/title when external confidence is <85%, records telemetry, and accelerates repeat lookups via cache.

### Tests for User Story 4 ⚠️

- [X] T029 [P] [US4] Unit test confidence thresholding (external override vs local preservation) in tests/unit/metadata/test_confidence_resolution.py
- [X] T034 [P] [US4] Integration test for CLI options, cache hits, dry-run simulation, and offline fallback in tests/integration/test_audiobook_cli.py

### Implementation for User Story 4

- [X] T030 [US4] Enforce 85% threshold logic and partial non-conflicting metadata enrichment in media_cron/metadata/identifier.py
- [X] T031 [US4] Implement diagnostic CLI command media-cron test-book-lookup in media_cron/cli.py
- [X] T032 [US4] Add CLI flags (--audiobook-lookup, --audiobook-provider, --audiobook-confidence-threshold, --audiobook-cache) to media_cron/cli.py
- [X] T033 [US4] Wire audiobook_summary into BatchSummary reporting and JSON output in media_cron/pipeline.py

**Checkpoint**: Ambiguity resolution, telemetry, CLI diagnostics, and caching fully integrated

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, validation suite, and code quality verification

- [X] T035 [P] Author documentation guide for authoring and registering custom metadata providers in media_cron/metadata/README.md
- [X] T036 Implement and verify end-to-end quickstart scenarios 1-4 in tests/integration/test_audiobook_quickstart.py
- [X] T037 Run complete test suite and linters via pytest and ruff check . and ruff format .

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phases 3-6)**: All depend on Foundational phase completion
  - Phase 3 (US1) delivers the baseline single-file MVP
  - Phase 4 (US2) builds upon US1 to support multi-file directories
  - Phase 5 (US3) adds Audnexus and priority cascade
  - Phase 6 (US4) finalizes confidence thresholds, CLI flags, and telemetry
- **Polish (Phase 7)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Depends on Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Depends on US1 identifier engine - Adds bundle clustering
- **User Story 3 (P3)**: Depends on US1 provider framework - Adds second provider and cascade
- **User Story 4 (P4)**: Depends on US1-US3 - Enforces threshold guards, CLI, and telemetry

### Parallel Opportunities

- **Phase 1**: T003 can run in parallel with T002
- **Phase 2**: T004, T005, T006, T007, T008, T009, T010 can be developed and tested in parallel
- **Phase 3 (US1)**: Test tasks T011, T012, T015, T018 can be written in parallel before implementation
- **Phase 4 (US2)**: Test task T019 and implementation T020 can run in parallel
- **Phase 5 (US3)**: T023 and T024 can run in parallel with T026
- **Phase 6 (US4)**: T029 and T034 test suites can be written in parallel

---

## Parallel Example: User Story 1

```bash
# Launch test creation in parallel:
Task: "Contract test for MetadataProviderProtocol in tests/contract/test_metadata_provider_contract.py"
Task: "Unit test OpenLibraryProvider in tests/unit/metadata/test_openlibrary_provider.py"

# Implement Open Library provider and identifier in sequence:
Task: "Implement OpenLibraryProvider in media_cron/metadata/providers/openlibrary.py"
Task: "Implement AudiobookIdentifier in media_cron/metadata/identifier.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T003)
2. Complete Phase 2: Foundational (T004-T010)
3. Complete Phase 3: User Story 1 (T011-T018)
4. **STOP and VALIDATE**: Run `pytest tests/unit/metadata/ tests/contract/test_metadata_provider_contract.py tests/integration/test_audiobook_single_file.py`
5. Verify single-file `.m4b` identification against Open Library (MVP ready!)

### Incremental Delivery

1. Phase 1 + 2: Foundation ready (models, protocols, cache, scorer)
2. Phase 3 (US1): Single-file identification working end-to-end
3. Phase 4 (US2): Multi-file chapter bundles clustered via album tag consensus
4. Phase 5 (US3): Audnexus provider and cascade prioritization enabled
5. Phase 6 (US4): Strict 85% threshold, CLI options, and telemetry reporting
6. Phase 7: Quickstart end-to-end tests and documentation
