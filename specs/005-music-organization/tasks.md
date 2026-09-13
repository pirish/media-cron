# Tasks: Music Library Organization and Drop-Folder Ingestion

**Feature**: `005-music-organization`
**Date**: 2026-09-09
**Specification**: [spec.md](spec.md)
**Implementation Plan**: [plan.md](plan.md)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project layout, models, configuration schemas, and telemetry extensions.

- [X] T001 Initialize music metadata directory layout and module stubs in media_cron/metadata/
- [X] T002 [P] Define MusicWorkflowMode, MusicFormat, CompanionAssetType, MusicTrack, MusicCompanionAsset, MusicReleaseBundle, MusicCatalogMatch, and MusicSpoolResult domain models in media_cron/metadata/models.py
- [X] T003 [P] Extend MusicConfig in media_cron/config.py and register music_summary in BatchSummary in media_cron/models.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Protocols, configuration validation, and persistent caching infrastructure.

**⚠️ CRITICAL**: Must be completed before any user story implementation can proceed.

- [X] T004 [P] Define MusicSpoolEngineProtocol and MusicMetadataProviderProtocol in media_cron/metadata/base.py
- [X] T005 [P] Unit test music domain models and configuration defaults in tests/unit/metadata/test_music_models.py and tests/unit/metadata/test_music_config.py
- [X] T006 Implement music metadata query caching in media_cron/metadata/cache.py
- [X] T007 [P] Unit test music cache key generation, TTL validation, and atomic writes in tests/unit/metadata/test_music_cache.py

**Checkpoint**: Foundation ready - user story implementation can now begin.

---

## Phase 3: User Story 1 - Drop-Folder Ingestion for External Music Managers (Priority: P1) 🎯 MVP

**Goal**: Ingest music releases from staging and deposit them into an external music manager's drop folder (e.g. `beets`) with folder hierarchy, companion assets, atomic hidden staging (`.incoming_<release>`), and optional post-ingest command execution.

**Independent Test**: Provide an album directory containing audio tracks and cover artwork in staging; process in spool mode; verify that the complete release folder hierarchy and companion assets are deposited atomically into the drop directory with zero corrupted or partial files, leaving source intact.

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation (Constitution Principle II)**

- [X] T008 [P] [US1] Author contract test for MusicSpoolEngineProtocol in tests/contract/test_music_spooler_contract.py
- [X] T009 [P] [US1] Author unit test for companion file bundling and release folder aggregation in tests/unit/metadata/test_music_bundler.py
- [X] T010 [P] [US1] Author unit test for atomic directory staging (.incoming_*) and post-ingest command execution in tests/unit/metadata/test_music_spooler.py
- [X] T011 [US1] Author integration test for drop-folder spooling and companion asset preservation in tests/integration/test_music_spool.py

### Implementation for User Story 1

- [X] T012 [US1] Implement MusicReleaseBundleAggregator in media_cron/metadata/music_bundler.py clustering tracks, disc subdirectories, and companion assets (.jpg, .png, .cue, .log, .m3u)
- [X] T013 [US1] Implement MusicSpoolEngine in media_cron/metadata/music_spooler.py with atomic hidden directory staging, hardlink transfer with copy fallback, and post-ingest command execution
- [X] T014 [US1] Implement MusicLookupPlugin in media_cron/plugins/lookup/music.py handling audio track and companion file routing in spool mode
- [X] T015 [US1] Register MusicLookupPlugin and wire drop-folder spooling into media_cron/pipeline.py

**Checkpoint**: User Story 1 is fully functional as an independently testable MVP.

---

## Phase 4: User Story 2 - Automated Embedded Metadata Extraction & Direct Organization (Priority: P2)

**Goal**: Extract embedded tags (artist, album artist, album, title, track/disc number, year, genre) across audio formats using `tinytag` and regex filename heuristics, organizing tracks directly into `Music/<Artist>/<Album> (<Year>)/<Track#> - <Title>.<ext>`.

**Independent Test**: Ingest audio files with embedded tags into direct organization mode; verify tracks are sorted into proper Artist/Album folders and tagged properly with compilation ("Various Artists") and multi-disc handling.

### Tests for User Story 2

- [X] T016 [P] [US2] Author unit test for MusicMetadataReader extracting ID3/Vorbis/FLAC/MP4 tags and regex fallback in tests/unit/metadata/test_music_reader.py
- [X] T017 [P] [US2] Author unit test for direct library path formatting and compilation grouping in tests/unit/metadata/test_music_direct_naming.py
- [X] T018 [US2] Author integration test for direct library organization in tests/integration/test_music_direct.py

### Implementation for User Story 2

- [X] T019 [US2] Implement MusicMetadataReader in media_cron/metadata/music_reader.py wrapping tinytag and filename heuristics for .mp3, .flac, .m4a, .ogg, .opus, .wav, .alac, .aiff
- [X] T020 [US2] Extend MusicLookupPlugin in media_cron/plugins/lookup/music.py to format destination paths and organize directly into target library folders

**Checkpoint**: User Stories 1 and 2 both operate independently.

---

## Phase 5: User Story 3 - Optional External Catalog Identification (Priority: P3)

**Goal**: Optional online release and tracklist identification using a multi-provider cascade (MusicBrainz keyless primary, Discogs optional authenticated fallback) with $\ge 85\%$ confidence thresholding and offline fallback.

**Independent Test**: Ingest an album with partial tags with external lookup enabled; verify MusicBrainz queries resolve canonical release details and populate missing fields while preserving local tags when below threshold.

### Tests for User Story 3

- [X] T021 [P] [US3] Author contract test for MusicMetadataProviderProtocol in tests/contract/test_music_provider_contract.py
- [X] T022 [P] [US3] Author unit test for MusicBrainzProvider (queries, throttling, XML/JSON parsing) in tests/unit/metadata/test_musicbrainz_provider.py
- [X] T023 [P] [US3] Author unit test for DiscogsProvider (token auth, candidate search) in tests/unit/metadata/test_discogs_provider.py
- [X] T024 [P] [US3] Author unit test for MusicIdentifier confidence scoring and threshold cascade in tests/unit/metadata/test_music_identifier.py
- [X] T025 [US3] Author integration test for provider cascade and offline fallback in tests/integration/test_music_catalog.py

### Implementation for User Story 3

- [X] T026 [US3] Implement MusicBrainzProvider in media_cron/metadata/providers/musicbrainz.py with 1 req/s rate limiting and persistent caching
- [X] T027 [US3] Implement DiscogsProvider in media_cron/metadata/providers/discogs.py supporting personal access token authentication
- [X] T028 [US3] Implement MusicIdentifier in media_cron/metadata/music_identifier.py coordinating local tags, cache queries, provider cascade, and confidence resolution
- [X] T029 [US3] Integrate MusicIdentifier into MusicLookupPlugin in media_cron/plugins/lookup/music.py for direct and hybrid modes

**Checkpoint**: All three operational modes (spool, direct, hybrid) functional with optional catalog enrichment.

---

## Phase 6: User Story 4 - Non-Destructive Simulation, CLI Options & Telemetry (Priority: P4)

**Goal**: Complete CLI options, diagnostic commands (`test-music-identify`, `test-music-spool`), 100% predictive `--dry-run` simulation, and telemetry summary reporting.

**Independent Test**: Execute `media-cron process --dry-run` and diagnostic CLI commands against music directories; verify complete planned operations without writing or moving any files.

### Tests for User Story 4

- [X] T030 [P] [US4] Author unit tests for diagnostic commands (test-music-identify, test-music-spool) in tests/unit/metadata/test_music_cli_diagnostics.py
- [X] T031 [US4] Author integration tests for CLI flags (--music-mode, --music-spool-dir, --music-post-command, --music-lookup, --dry-run) in tests/integration/test_music_cli.py

### Implementation for User Story 4

- [X] T032 [US4] Implement CLI commands test-music-identify and test-music-spool in media_cron/cli.py with text and JSON output
- [X] T033 [US4] Add CLI flags --music/--no-music, --music-mode, --music-spool-dir, --music-post-command, --music-lookup to media_cron/cli.py
- [X] T034 [US4] Wire music_summary telemetry into media_cron/pipeline.py and enforce dry-run simulation mode

**Checkpoint**: Full CLI ergonomics, diagnostics, and simulation modes verified.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, validation suite, and code quality verification.

- [X] T035 [P] Author documentation guide for music drop-folder spooling, beets integration, and direct organization in media_cron/metadata/MUSIC.md
- [X] T036 Implement and verify end-to-end quickstart scenarios 1-5 in tests/integration/test_music_quickstart.py
- [X] T037 Run complete test suite and code quality gates via pytest and ruff check . and ruff format .

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phases 3-6)**: All depend on Foundational phase completion
  - Phase 3 (US1) delivers the drop-folder ingestion MVP
  - Phase 4 (US2) delivers autonomous embedded tag library organization
  - Phase 5 (US3) enriches US1-US2 with optional MusicBrainz/Discogs catalog lookup
  - Phase 6 (US4) finalizes CLI ergonomics, diagnostics, dry-run safety, and telemetry
- **Polish (Phase 7)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Depends on Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Depends on Foundational (Phase 2) - Independently testable
- **User Story 3 (P3)**: Depends on US1/US2 - Adds external catalog enrichment
- **User Story 4 (P4)**: Depends on US1-US3 - Enforces CLI options, dry-run mode, and telemetry

### Parallel Opportunities

- **Phase 1**: T002 and T003 can run in parallel
- **Phase 2**: T004, T005, and T007 can run in parallel
- **Phase 3 (US1)**: Test tasks T008, T009, T010 can be authored in parallel before implementation
- **Phase 4 (US2)**: Test tasks T016 and T017 can run in parallel
- **Phase 5 (US3)**: Test tasks T021, T022, T023, T024 can run in parallel
- **Phase 6 (US4)**: Test task T030 can run in parallel with foundational tests

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 in parallel:
Task: "Author contract test for MusicSpoolEngineProtocol in tests/contract/test_music_spooler_contract.py"
Task: "Author unit test for companion file bundling in tests/unit/metadata/test_music_bundler.py"
Task: "Author unit test for atomic directory staging in tests/unit/metadata/test_music_spooler.py"

# Implement bundler, spool engine, and plugin in sequence:
Task: "Implement MusicReleaseBundleAggregator in media_cron/metadata/music_bundler.py"
Task: "Implement MusicSpoolEngine in media_cron/metadata/music_spooler.py"
Task: "Implement MusicLookupPlugin in media_cron/plugins/lookup/music.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T003)
2. Complete Phase 2: Foundational (T004-T007)
3. Complete Phase 3: User Story 1 (T008-T015)
4. **STOP and VALIDATE**: Run `pytest tests/contract/test_music_spooler_contract.py tests/unit/metadata/test_music_bundler.py tests/unit/metadata/test_music_spooler.py tests/integration/test_music_spool.py`
5. Verify clean drop-folder handoff with atomic staging and companion asset preservation (MVP ready for `beets`!)

### Incremental Delivery

1. Phase 1 + 2: Foundation ready (models, protocols, cache, config)
2. Phase 3 (US1): External drop-folder spooling with atomic staging and post-command execution
3. Phase 4 (US2): Direct library organization with embedded tag extraction
4. Phase 5 (US3): Optional online catalog lookups via MusicBrainz / Discogs cascade
5. Phase 6 (US4): Complete CLI options, diagnostic commands, dry-run safety, and telemetry
6. Phase 7: End-to-end quickstart validation and documentation

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- In accordance with Constitution Principle II (TDD), tests MUST be written and fail before implementation
- All drop-folder operations MUST employ hidden directory atomic staging to prevent inotify watcher races (Constitution Principle III)
