# Tasks: Torrent Client Integration for Ingestion and Seeding Management

**Branch**: `002-torrent-client-integration` | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Initialize torrent client module structure and configuration extensions

- [X] T001 Create directory structure for torrent client module (`media_cron/torrent/`, `media_cron/torrent/clients/`, `tests/unit/torrent/`) per plan.md
- [X] T002 Update configuration models in media_cron/config.py to support `active_torrent_client`, `hybrid_ingest`, `torrent_clients` dictionaries, and `MEDIA_CRON_*` environment variable overrides

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core torrent models, protocol interfaces, client registry, and path translation that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T003 [P] Implement core torrent data models (`TorrentState`, `TorrentFile`, `TorrentItem`, `PathMappingRule`, `TorrentClientConfig`, `TorrentFilterConfig`, `TorrentSeedingConfig`) in media_cron/torrent/models.py
- [X] T004 [P] Implement `TorrentClientProtocol` and `TorrentClientRegistry` in media_cron/torrent/base.py
- [X] T005 [P] Implement unit tests for `PathMappingRule.translate()` and path normalization in tests/unit/test_path_mapping.py
- [X] T006 [P] Implement unit tests for `TorrentItem` completion and health validation checks in tests/unit/test_torrent_models.py
- [X] T007 [P] Implement unit tests for `TorrentClientRegistry` registration and lookup in tests/unit/test_torrent_registry.py

**Checkpoint**: Foundation ready — user story implementation can now begin in parallel or sequentially

---

## Phase 3: User Story 1 - Direct Ingestion from qBittorrent (Priority: P1) 🎯 MVP

**Goal**: Query qBittorrent Web API v2 for completed torrents, apply path mappings, copy payload files to `staging_dir` for isolated processing, and support targeted single-torrent ingestion by hash or name.

**Independent Test**: Connect to a qBittorrent instance containing a 100% completed torrent; run `media-cron run --torrent-client qbittorrent --staging-dir <staging> --dry-run`; verify discovered torrents and staging operations are planned without touching incomplete torrents.

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T008 [P] [US1] Write contract tests for `TorrentClientProtocol` compliance using mock client responses in tests/contract/test_torrent_client_contract.py
- [X] T009 [P] [US1] Write unit tests for `QBittorrentClient` (login authentication, listing completed torrents, fetching files, hash/name lookup, error handling) in tests/unit/test_qbittorrent_client.py
- [X] T010 [P] [US1] Write integration test for qBittorrent payload copying to staging directory in tests/integration/test_qbittorrent_staging.py
- [X] T011 [P] [US1] Write integration test for targeted single-torrent ingestion by hash and name in tests/integration/test_targeted_ingest.py

### Implementation for User Story 1

- [X] T012 [P] [US1] Implement `QBittorrentClient` using stdlib `urllib.request` and `CookieJar` in media_cron/torrent/clients/qbittorrent.py
- [X] T013 [P] [US1] Register `QBittorrentClient` in `TorrentClientRegistry` on package import in media_cron/torrent/__init__.py
- [X] T014 [US1] Implement `TorrentInputPlugin` conforming to `InputPlugin` protocol to discover completed torrents and copy payloads to staging in media_cron/plugins/input/torrent.py
- [X] T015 [US1] Extend `Pipeline` to support `TorrentInputPlugin` execution and targeted single-torrent filtering in media_cron/pipeline.py
- [X] T016 [US1] Extend CLI `run` command with `--torrent-client`, `--torrent-hash`, and `--torrent-name` options in media_cron/cli.py
- [X] T017 [US1] Implement CLI `test-client` command for connection and authentication diagnostics in media_cron/cli.py

**Checkpoint**: At this point, User Story 1 is fully functional as a standalone qBittorrent ingestion engine (MVP complete).

---

## Phase 4: User Story 2 - Torrent Client-Managed Seeding Relocation (Priority: P2)

**Goal**: Relocate completed torrent storage to a dedicated seed directory (or destination library) using qBittorrent's `setLocation` API, preserving non-media clutter in seeding storage for 100% tracker verification.

**Independent Test**: Execute `media-cron run --torrent-client qbittorrent --seeding-mode client_relocate --seed-dir <dir>`; verify qBittorrent receives `setLocation`, storage is relocated, clutter files remain intact in the seeding path, and seeding resumes without hash errors.

### Tests for User Story 2 ⚠️

- [X] T018 [P] [US2] Write unit tests for `QBittorrentClient.relocate_storage()` handling success, timeouts, and client I/O errors in tests/unit/test_qbittorrent_relocate.py
- [X] T019 [P] [US2] Write contract test for torrent seeding output plugin in tests/contract/test_torrent_seed_contract.py
- [X] T020 [P] [US2] Write integration test for client-managed relocation with clutter preservation in tests/integration/test_client_relocation.py

### Implementation for User Story 2

- [X] T021 [P] [US2] Implement `relocate_storage` method in `QBittorrentClient` (`/api/v2/torrents/setLocation`) in media_cron/torrent/clients/qbittorrent.py
- [X] T022 [US2] Implement `TorrentClientSeedOutput` conforming to `OutputPlugin` for commanding client storage relocation in media_cron/plugins/output/torrent_seed.py
- [X] T023 [US2] Update pipeline output orchestration to dispatch `TorrentClientSeedOutput` when `seeding.mode == "client_relocate"` in media_cron/pipeline.py
- [X] T024 [US2] Extend CLI `run` command with `--seeding-mode [client_relocate|direct_filesystem|none]` flag in media_cron/cli.py

**Checkpoint**: User Stories 1 AND 2 work together. Torrents are ingested, organized, and their active seeding storage is safely relocated via client API.

---

## Phase 5: User Story 3 - Idempotent Tagging and Torrent State Lifecycle (Priority: P3)

**Goal**: Perform dual status update in the torrent client (tag `media-cron-processed` AND category `media-cron-done`) upon successful organization, skip already processed torrents on subsequent runs, and optionally pause torrents.

**Independent Test**: Ingest and organize a completed torrent; verify tag `media-cron-processed` and category `media-cron-done` are applied; run ingestion again immediately and verify that the tagged torrent is skipped with 0 redundant operations.

### Tests for User Story 3 ⚠️

- [X] T025 [P] [US3] Write unit tests for `QBittorrentClient.apply_completion_state()` (tags, categories, pause) in tests/unit/test_qbittorrent_tagging.py
- [X] T026 [P] [US3] Write integration test for recurring run idempotency (asserting zero re-ingestions of tagged/categorized torrents) in tests/integration/test_torrent_idempotency.py

### Implementation for User Story 3

- [X] T027 [P] [US3] Implement `apply_completion_state`, `add_tags`, `set_category`, and `pause_torrent` in `QBittorrentClient` in media_cron/torrent/clients/qbittorrent.py
- [X] T028 [US3] Update `TorrentClientSeedOutput` to execute dual tag and category updates and optional pause in media_cron/plugins/output/torrent_seed.py
- [X] T029 [US3] Update `TorrentInputPlugin` filter logic to exclude torrents with completion tag or completion category in media_cron/plugins/input/torrent.py

**Checkpoint**: Recurring cron executions are 100% idempotent. Processed torrents are tagged, re-categorized, and skipped on all subsequent runs.

---

## Phase 6: User Story 4 - Hybrid Ingestion (Folders and Torrent Clients) (Priority: P4)

**Goal**: Support simultaneous folder monitoring (`--source-dir`) and torrent client ingestion in a single coordinated pipeline run without collisions or duplicate staging.

**Independent Test**: Provide both a monitored drop folder with a video file and a completed torrent in qBittorrent; run `media-cron run --hybrid`; verify both sources are staged, organized into the library, and reported in the consolidated summary.

### Tests for User Story 4 ⚠️

- [X] T030 [P] [US4] Write integration test for hybrid ingestion combining `DirectoryScannerInput` and `TorrentInputPlugin` in tests/integration/test_hybrid_pipeline.py
- [X] T031 [P] [US4] Write unit test for staging path deduplication across multiple input plugins in tests/unit/test_staging_dedup.py

### Implementation for User Story 4

- [X] T032 [US4] Extend `Pipeline.run()` to orchestrate multiple input plugins sequentially when `hybrid_ingest` is enabled in media_cron/pipeline.py
- [X] T033 [US4] Implement deduplication check in `Pipeline` to prevent staging duplicate files from overlapping directory and torrent paths in media_cron/pipeline.py
- [X] T034 [US4] Extend CLI `run` command with `--hybrid / --no-hybrid` toggle in media_cron/cli.py

**Checkpoint**: Dropped local files and remote torrent downloads can be ingested concurrently in a single invocation.

---

## Phase 7: User Story 5 - Pluggable Client Architecture (Transmission and Deluge Extensibility) (Priority: P5)

**Goal**: Ensure generic `TorrentClientProtocol` and `TorrentClientRegistry` fully abstract client operations so external Transmission and Deluge plugins can be registered without modifying pipeline code.

**Independent Test**: Register mock Transmission and Deluge client adapters conforming to `TorrentClientProtocol`; verify discovery, relocation, and tagging execute identically to built-in qBittorrent.

### Tests for User Story 5 ⚠️

- [X] T035 [P] [US5] Write contract tests verifying that a mock `TransmissionClient` and `DelugeClient` satisfy `TorrentClientProtocol` in tests/contract/test_mock_clients_contract.py
- [X] T036 [P] [US5] Write unit tests for invalid client provider rejection and available provider listing in tests/unit/test_client_provider_errors.py

### Implementation for User Story 5

- [X] T037 [P] [US5] Implement factory validation and error handling for unsupported client providers in media_cron/torrent/base.py
- [X] T038 [US5] Document pluggable client development and registration guidelines in media_cron/torrent/README.md

**Checkpoint**: External plugins can implement Transmission and Deluge adapters against the documented contract.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Telemetry, security credential masking, documentation, and end-to-end scenario verification

- [X] T039 [P] Extend JSON telemetry in `BatchSummary` with `torrent_summary` metrics in media_cron/models.py
- [X] T040 [P] Implement password and token masking for torrent client credentials in logs and console output in media_cron/config.py
- [X] T041 [P] Validate all end-to-end scenarios against quickstart.md using pytest in tests/integration/test_quickstart_scenarios.py
- [X] T042 Run ruff linting and formatting across all new and updated files (`ruff check .`, `ruff format --check .`)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories.
- **User Stories (Phase 3+)**: All depend on Foundational phase completion:
  - **User Story 1 (P1)**: Ingestion baseline (MVP).
  - **User Story 2 (P2)**: Relocation output (depends on US1 models and client).
  - **User Story 3 (P3)**: State tagging (builds on US1 & US2 client methods).
  - **User Story 4 (P4)**: Hybrid ingestion (combines US1 with existing directory scanner).
  - **User Story 5 (P5)**: Pluggable contracts (generalizes client registry).
- **Polish (Phase 8)**: Depends on all desired user stories being complete.

### User Story Dependencies

```mermaid
graph TD
    P1[Phase 1: Setup] --> P2[Phase 2: Foundational]
    P2 --> US1[Phase 3: US1 - qBittorrent Ingestion (MVP)]
    US1 --> US2[Phase 4: US2 - Seeding Relocation]
    US2 --> US3[Phase 5: US3 - Idempotent Tagging]
    US1 --> US4[Phase 6: US4 - Hybrid Ingestion]
    P2 --> US5[Phase 7: US5 - Pluggable Clients]
    US3 --> Polish[Phase 8: Polish & Cross-Cutting]
    US4 --> Polish
    US5 --> Polish
```

---

## Parallel Opportunities

- **Phase 2 (Foundational)**: T003, T004, T005, T006, T007 can all run in parallel.
- **Phase 3 (User Story 1)**:
  - Tests T008, T009, T010, T011 can be written concurrently.
  - Client T012 and Registry registration T013 can be implemented in parallel with plugin T014.
- **Phase 4 (User Story 2)**: Tests T018, T019, T020 can be written in parallel.
- **Phase 5 (User Story 3)**: Tests T025, T026 can be written in parallel.
- **Phase 6 (User Story 4)**: Tests T030, T031 can be written in parallel.
- **Phase 7 (User Story 5)**: Tests T035, T036 and implementation T037 can run concurrently.
- **Phase 8 (Polish)**: T039, T040, T041 can run in parallel.

---

## Implementation Strategy

### MVP First (User Story 1 Only)
1. Complete Phase 1: Setup (T001–T002)
2. Complete Phase 2: Foundational (T003–T007)
3. Complete Phase 3: User Story 1 (T008–T017)
4. **STOP and VALIDATE**: Verify qBittorrent completed download ingestion works end-to-end in `--dry-run` and live copy mode.

### Incremental Delivery
1. Add User Story 2 (T018–T024): Seeding relocation via client `setLocation`.
2. Add User Story 3 (T025–T029): Tag and category lifecycle for unattended cron idempotency.
3. Add User Story 4 (T030–T034): Hybrid folder + torrent client monitoring.
4. Add User Story 5 (T035–T038): Verification of Transmission and Deluge pluggable extensibility.
5. Complete Phase 8 (T039–T042): JSON telemetry, credential masking, linting, and quickstart validation.
