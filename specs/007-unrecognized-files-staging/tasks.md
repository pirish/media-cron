# Tasks: Unrecognized Media Staging and Interactive Manual Review

**Feature**: `007-unrecognized-files-staging`  
**Input**: Design artifacts from `specs/007-unrecognized-files-staging/` (`spec.md`, `plan.md`, `data-model.md`, `contracts/`, `quickstart.md`)  
**Status**: Ready for Implementation  

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, review configuration models, and directory structure.

- [X] T001 Add `PathsConfig.review_dir` and `ReviewConfig` models in media_cron/config.py
- [X] T002 [P] Initialize review package structure and exports in media_cron/review/__init__.py
- [X] T003 [P] Author unit tests for review configuration parsing, defaults, and env vars in tests/unit/review/test_review_config.py

---

## Phase 2: Foundational (Core Models & Protocols)

**Purpose**: Core data models, protocols, and category hint heuristics that MUST be complete before user stories begin.

**⚠️ CRITICAL**: No user story implementation can begin until this phase is complete.

- [X] T004 [P] Define ReviewStatus, ReviewAction, UnrecognizedFile, UserAnnotation, and ReviewManifest models in media_cron/review/models.py
- [X] T005 [P] Define ReviewManagerProtocol interface in media_cron/review/base.py
- [X] T006 [P] Author contract tests for ReviewManagerProtocol in tests/contract/test_review_manager_contract.py
- [X] T007 [P] Author unit tests for ReviewManifest serialization, schema validation, and models in tests/unit/review/test_review_models.py
- [X] T008 [P] Author unit tests for category hint extraction heuristics in tests/unit/review/test_review_heuristics.py
- [X] T009 Implement category hint heuristics in media_cron/review/heuristics.py

**Checkpoint**: Foundation ready - domain models, protocols, and heuristics verified. User story implementation can begin.

---

## Phase 3: User Story 1 - Automated Staging of Unrecognized Media (Priority: P1) 🎯 MVP

**Goal**: Automatically detect unrecognized items during pipeline runs and relocate them into `<review_dir>/<item_id>/` with an accompanying `manifest.json`, protecting active torrent seeds and supporting dry-run simulation.

**Independent Test**: Place unrecognized media files and active torrent seeds in staging. Execute `media-cron process --review-dir <dir>`. Verify unrecognized files are moved into isolated subdirectories in the review directory with valid `manifest.json`, torrent seeds are copied/hardlinked rather than moved, and telemetry records `unrecognized_count` and `review_staged_count`.

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T010 [P] [US1] Author unit tests for ReviewManager.stage_unrecognized (isolated subfolder, hidden staging .staging_*, atomic promotion, manifest generation) in tests/unit/review/test_review_staging.py
- [X] T011 [P] [US1] Author integration tests for pipeline unrecognized item detection, torrent seeding safety (copy/hardlink fallback), and dry-run simulation in tests/integration/test_unrecognized_staging.py

### Implementation for User Story 1

- [X] T012 [US1] Implement ReviewManager.stage_unrecognized with inotify-safe atomic staging in media_cron/review/manager.py
- [X] T013 [US1] Wire unrecognized item detection, review staging, and batch summary telemetry into media_cron/pipeline.py
- [X] T014 [US1] Add CLI flags --review-dir and --review-max-age-days to main CLI in media_cron/cli.py

**Checkpoint**: User Story 1 complete and independently testable (MVP delivery). Unrecognized files are safely routed to review.

---

## Phase 4: User Story 2 - Interactive CLI Review & Non-Interactive Commands (Priority: P2)

**Goal**: Provide an interactive guided terminal session (`media-cron review`) and non-interactive subcommands (`review list`, `review show`) for inspecting and annotating staged items.

**Independent Test**: Place items in review directory. Run `media-cron review list --format json` to verify machine-readable output. Run `media-cron review` in a TTY to verify interactive prompts for category and metadata.

### Tests for User Story 2 ⚠️

- [X] T015 [P] [US2] Author unit tests for review CLI commands (list, show, non-interactive flags, JSON output) in tests/unit/review/test_review_cli.py
- [X] T016 [P] [US2] Author unit tests for interactive review prompt handling and TTY fallback in tests/unit/review/test_review_interactive.py

### Implementation for User Story 2

- [X] T017 [US2] Implement ReviewManager.list_items and ReviewManager.get_item in media_cron/review/manager.py
- [X] T018 [US2] Implement non-interactive review CLI subcommands (list, show) with text and JSON output in media_cron/cli.py
- [X] T019 [US2] Implement interactive review terminal loop (media-cron review) with category selection and metadata prompts in media_cron/cli.py

**Checkpoint**: User Stories 1 and 2 complete. Items can be staged, listed, inspected, and annotated.

---

## Phase 5: User Story 3 - Resolution Actions, Media Server Rescan, & Retention Purge (Priority: P3)

**Goal**: Support immediate resolution actions (Organize Now with media server rescan, Return to Staging with hints, Discard, Skip) and age-based retention purging.

**Independent Test**: Review an item and select "Organize Now". Verify the file is organized into destination library matching configured templates, media server is notified, and status becomes `RESOLVED`. Test "Return to Staging" to verify `.media-cron-hint.json` generation. Test `review purge --older-than <days>` to verify stale item cleanup.

### Tests for User Story 3 ⚠️

- [X] T020 [P] [US3] Author unit tests for resolution actions (ORGANIZE_NOW, REINGEST, DISCARD, SKIP, and retention purge) in tests/unit/review/test_review_resolution.py
- [X] T021 [P] [US3] Author integration tests for end-to-end resolution (library organization, .media-cron-hint.json generation, media server rescan) in tests/integration/test_review_resolution.py

### Implementation for User Story 3

- [X] T022 [US3] Implement ReviewManager.resolve_item (ORGANIZE_NOW, REINGEST, DISCARD, SKIP) and media server notification dispatch in media_cron/review/manager.py
- [X] T023 [US3] Implement ReviewManager.purge_items for age-based retention in media_cron/review/manager.py
- [X] T024 [US3] Wire resolve, discard, reingest, and purge CLI subcommands into media_cron/cli.py

**Checkpoint**: All three user stories complete and fully functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, validation suite, and code quality verification.

- [X] T025 [P] Author comprehensive documentation guide for unrecognized media staging and manual review in media_cron/review/REVIEW.md
- [X] T026 Implement and verify end-to-end quickstart scenarios 1-5 in tests/integration/test_review_quickstart.py
- [X] T027 Run complete test suite and code quality gates via pytest, ruff check ., and ruff format .

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational completion - Delivers standalone staging MVP
- **User Story 2 (Phase 4)**: Depends on US1 (requires review directory and staged items)
- **User Story 3 (Phase 5)**: Depends on US2 (requires annotation models and CLI subcommands)
- **Polish (Phase 6)**: Depends on US1-US3 being complete

### User Story Dependencies

- **User Story 1 (P1)**: Independent of US2 and US3; implements automated isolation of unrecognized media.
- **User Story 2 (P2)**: Builds upon US1 review directory structure to provide inspection and annotation.
- **User Story 3 (P3)**: Executes resolution actions on annotations produced in US2.

### Parallel Opportunities

- **Phase 1**: T002 and T003 can execute in parallel once T001 is started.
- **Phase 2**: T004, T005, T006, T007, T008 can all run in parallel.
- **Phase 3 (US1)**: Test tasks T010 and T011 can run in parallel before implementation.
- **Phase 4 (US2)**: Test tasks T015 and T016 can run in parallel before implementation.
- **Phase 5 (US3)**: Test tasks T020 and T021 can run in parallel before implementation.

---

## Implementation Strategy

### MVP First (User Story 1 Only)
1. Complete Phase 1 (Setup) and Phase 2 (Foundational).
2. Complete Phase 3 (User Story 1).
3. Validate User Story 1 independently with `tests/integration/test_unrecognized_staging.py`.
4. Deployable MVP: Unrecognized media is safely sequestered into `review_dir` without blocking active staging.

### Incremental Delivery
1. Add User Story 2: Users can now inspect and annotate pending review items via CLI (`list`, `show`, `review`).
2. Add User Story 3: Users can execute resolutions (`Organize Now`, `Return to Staging`, `Discard`) and purge stale items.
3. Finalize with Phase 6: Quickstart validation scenarios 1–5, complete documentation, and quality gates.
