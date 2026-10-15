# Tasks: Fast Failure Recovery and Transfer Resumption

**Branch**: `011-resume-failed-transfers` | **Date**: 2026-10-15 | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Initialize recovery subsystem package structure, protocol contracts, and domain models.

- [X] T001 Create recovery package directory in `media_cron/recovery/` and test directories in `tests/contract/`, `tests/unit/recovery/`, and `tests/integration/`
- [X] T002 [P] Define domain enums and models in `media_cron/recovery/models.py` (`VerificationStatus`, `FileIntegrityRecord`, `VerificationResult`, `RecoverySummary`)
- [X] T003 [P] Define core recovery protocol in `media_cron/recovery/protocols.py` (`TransferVerifierProtocol`)
- [X] T004 Wire public package exports (`TransferVerifier`, `VerificationStatus`, `VerificationResult`, `RecoverySummary`) in `media_cron/recovery/__init__.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core verifier engine, streaming SHA-256 hashing, size-first fast rejection, and safe boundary containment that MUST be complete before ANY user story can be implemented.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T005 [P] Create contract tests for `TransferVerifierProtocol` in `tests/contract/test_recovery_contract.py`
- [X] T006 [P] Create unit tests for recovery models, validation invariants, and summary serialization in `tests/unit/recovery/test_recovery_models.py`
- [X] T007 [P] Implement streaming SHA-256 hash calculation with 1MB chunk buffer in `media_cron/recovery/verifier.py`
- [X] T008 [P] Implement size-first fast rejection and same-inode short-circuit checks in `media_cron/recovery/verifier.py`
- [X] T009 [P] Implement safe path containment and purge helpers (`purge_item`) preventing traversal outside staging/destination in `media_cron/recovery/verifier.py`
- [X] T010 Create unit tests for hashing, size-first checks, and safe boundary containment in `tests/unit/recovery/test_transfer_verifier.py` and `tests/unit/recovery/test_safe_purge.py`

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel or sequentially.

---

## Phase 3: User Story 1 - Resume Ingestion from Matching Staged Files (Priority: P1) 🎯 MVP

**Goal**: Skip re-copying queued files into staging when an existing file or multi-file directory in staging matches the source content hash, reducing intake time and disk I/O.

**Independent Test**: Place a test media file in source, pre-stage an identical copy in staging, run pipeline; verify staged file is validated, re-copy is skipped, and pipeline advances directly to planning.

### Tests for User Story 1 ⚠️
> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T011 [P] [US1] Create unit tests for multi-file directory and single-file integrity evaluation in `tests/unit/recovery/test_staged_item_matching.py`
- [X] T012 [P] [US1] Create integration tests for staging resume across `TorrentInputPlugin` and `DirectoryScannerInputPlugin` in `tests/integration/test_staging_recovery_flow.py`

### Implementation for User Story 1

- [X] T013 [US1] Implement `verify_directory()` for recursive multi-file release bundle validation in `media_cron/recovery/verifier.py`
- [X] T014 [US1] Integrate `TransferVerifier` into `TorrentInputPlugin.discover()` to check candidate `staging_dest` and resume without copying in `media_cron/plugins/input/torrent.py`
- [X] T015 [US1] Integrate `TransferVerifier` into `DirectoryScannerInputPlugin.discover()` to check matching staged files before moving/copying in `media_cron/plugins/input/directory.py`

**Checkpoint**: At this point, User Story 1 is fully functional and delivers an immediate MVP for resuming interrupted staging operations.

---

## Phase 4: User Story 2 - Clean Purge and Restart on Corrupted or Incomplete Staged Files (Priority: P2)

**Goal**: Detect partial, truncated, or corrupted files/directories in staging via size-first fast check and hash check, safely purge them, and restart transfer cleanly from scratch.

**Independent Test**: Place a valid file in source, create a truncated version in staging; run pipeline; verify size mismatch is detected, corrupt staged file is deleted, and clean copy is made from source.

### Tests for User Story 2 ⚠️
> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T016 [P] [US2] Create unit tests for detecting size mismatches and hash mismatches in staged items in `tests/unit/recovery/test_corrupt_staging_detection.py`
- [X] T017 [P] [US2] Create integration tests for corrupt staging purge and fresh restart in `tests/integration/test_corrupt_staging_purge.py`

### Implementation for User Story 2

- [X] T018 [US2] Implement corrupt staging purge and fresh copy fallback in `TorrentInputPlugin.discover()` in `media_cron/plugins/input/torrent.py`
- [X] T019 [US2] Implement corrupt staging purge and fresh move fallback in `DirectoryScannerInputPlugin.discover()` in `media_cron/plugins/input/directory.py`
- [X] T020 [US2] Ensure multi-file directory atomic restart purges the entire release folder in staging on any constituent failure in `media_cron/recovery/verifier.py`

**Checkpoint**: User Stories 1 and 2 work together, providing complete resilience and self-healing for the staging directory.

---

## Phase 5: User Story 3 - Bypass Redundant Transfers for Already-Organized Destination Files (Priority: P3)

**Goal**: When destination file matches the source hash, bypass destination write, record transfer satisfied, and execute all remaining post-transfer actions (torrent seed relocation, source cleanup, notifications).

**Independent Test**: Pre-create destination file matching source hash; run pipeline; verify destination write bypassed, torrent seeding relocated, and source cleaned up in move mode.

### Tests for User Story 3 ⚠️
> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T021 [P] [US3] Create unit tests for destination content hash matching in `tests/unit/recovery/test_destination_verifier.py`
- [x] T022 [P] [US3] Create integration tests for destination transfer bypass and post-transfer seeding relocation in `tests/integration/test_destination_bypass_flow.py`

### Implementation for User Story 3

- [x] T023 [US3] Update `LibraryOrganizerOutput.execute()` to verify destination candidate via `TransferVerifier` and return satisfied result without rewriting in `media_cron/plugins/output/organizer.py`
- [x] T024 [US3] Update `VideoSpoolEngine` to verify existing spool targets and bypass redundant writes in `media_cron/metadata/video_spooler.py`
- [x] T025 [US3] Update `media_cron/pipeline.py` execution loop to ensure bypassed destination operations trigger downstream `TorrentClientSeedOutput` relocation and source cleanup

**Checkpoint**: User Stories 1, 2, and 3 provide end-to-end recovery across both staging intake and final library placement.

---

## Phase 6: User Story 4 - Purge and Re-transfer Corrupted Destination Files (Priority: P4)

**Goal**: When an existing destination file has size or hash mismatch, safely delete the invalid destination artifact before initiating a fresh transfer.

**Independent Test**: Place a truncated/corrupt file at destination path; run pipeline; verify invalid destination file is deleted and replaced with valid source payload.

### Tests for User Story 4 ⚠️
> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T026 [P] [US4] Create unit tests for corrupt destination detection and deletion in `tests/unit/recovery/test_destination_purge.py`
- [x] T027 [P] [US4] Create integration tests for destination corrupt file replacement in `tests/integration/test_destination_corruption_recovery.py`

### Implementation for User Story 4

- [x] T028 [US4] Add safe destination purge and fresh transfer retry logic to `LibraryOrganizerOutput.execute()` in `media_cron/plugins/output/organizer.py`
- [x] T029 [US4] Add permission and lock error handling around destination purge operations, halting dirty writes with explicit diagnostics in `media_cron/plugins/output/organizer.py`

**Checkpoint**: User Stories 1 through 4 ensure both staging and destination environments remain strictly clean and free of corrupted media.

---

## Phase 7: User Story 5 - Observability, Recovery Telemetry, and Dry-Run Reporting (Priority: P5)

**Goal**: Provide visibility into recovery events, bytes saved, and purge actions via structured logs, batch summary telemetry, and non-destructive dry-run simulation.

**Independent Test**: Run batch with mix of resumable and corrupt files in dry-run and live modes; verify structured logs and batch summary accurately report items resumed, purged, and bytes saved.

### Tests for User Story 5 ⚠️
> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T030 [P] [US5] Create unit tests for `RecoverySummary` tracking and formatting in `tests/unit/recovery/test_recovery_telemetry.py`
- [x] T031 [P] [US5] Create integration tests for recovery dry-run reporting and telemetry output in `tests/integration/test_recovery_dry_run.py`

### Implementation for User Story 5

- [x] T032 [US5] Integrate `recovery_summary` into `BatchSummary` dataclass and CLI human-readable summary formatter in `media_cron/models.py` and `media_cron/pipeline.py`
- [x] T033 [US5] Add recovery telemetry fields to machine-readable JSON batch export in `media_cron/pipeline.py`
- [x] T034 [US5] Implement non-destructive dry-run simulation across `TransferVerifier.verify_item()` and `TransferVerifier.purge_item()` in `media_cron/recovery/verifier.py`
- [x] T035 [US5] Add structured operational logging for all recovery, bypass, and purge events in `media_cron/recovery/verifier.py` and `media_cron/pipeline.py`

**Checkpoint**: All user stories functional with full observability and non-destructive dry-run verification.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: End-to-end verification, test suite regression checks, and documentation.

- [x] T036 [P] Execute end-to-end quickstart validation scenarios from `specs/011-resume-failed-transfers/quickstart.md`
- [x] T037 [P] Run full test suite (`pytest`) and linting (`ruff check`) ensuring 100% pass and no regressions across existing test suite
- [x] T038 Update documentation and review workflow notes in `docs/` and `README.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately.
- **Foundational (Phase 2)**: Depends on Setup (Phase 1) - **BLOCKS** all user stories.
- **User Stories (Phases 3–7)**: Depend on Foundational (Phase 2) completion.
  - User stories can proceed sequentially (US1 → US2 → US3 → US4 → US5) or in parallel.
- **Polish (Phase 8)**: Depends on all desired user stories being complete.

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2). No dependency on other stories.
- **User Story 2 (P2)**: Extends US1 ingestion recovery with corrupt purging. Can start after Phase 2.
- **User Story 3 (P3)**: Operates on destination organizer and pipeline loop. Can start after Phase 2.
- **User Story 4 (P4)**: Extends US3 destination checks with corrupt destination purging. Can start after Phase 2.
- **User Story 5 (P5)**: Hooks telemetry and dry-run into verifier and pipeline. Can start after Phase 2.

### Within Each User Story

- Tests MUST be authored and verified failing before implementation (Constitution Principle II).
- Core verifier logic before plugin integration.
- Unit tests before integration tests.

### Parallel Opportunities

- Phase 1: `T002` and `T003` can be implemented in parallel.
- Phase 2: `T005`, `T006`, `T007`, `T008`, and `T009` can be developed in parallel once models and protocols are defined.
- Within Story Phases: All test tasks marked `[P]` can run in parallel before implementation tasks.
- Polish: `T036` and `T037` can be executed in parallel.

---

## Parallel Example: User Story 1

```bash
# Launch tests for User Story 1 together:
Task: "Create unit tests for multi-file directory and single-file integrity evaluation in tests/unit/recovery/test_staged_item_matching.py"
Task: "Create integration tests for staging resume across TorrentInputPlugin and DirectoryScannerInputPlugin in tests/integration/test_staging_recovery_flow.py"

# Implement verifier directory support:
Task: "Implement verify_directory() for recursive multi-file release bundle validation in media_cron/recovery/verifier.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (`T001`–`T004`).
2. Complete Phase 2: Foundational (`T005`–`T010`).
3. Complete Phase 3: User Story 1 (`T011`–`T015`).
4. **STOP and VALIDATE**: Verify that pre-staged files in `staging_dir` are resumed without re-copying.
5. Deploy MVP increment.

### Incremental Delivery

1. Complete Setup + Foundational $\rightarrow$ Foundation verified with contract tests.
2. Add User Story 1 $\rightarrow$ Fast resume from staging working (MVP!).
3. Add User Story 2 $\rightarrow$ Corrupt staging purge and clean restart working.
4. Add User Story 3 $\rightarrow$ Destination bypass and post-transfer actions working.
5. Add User Story 4 $\rightarrow$ Corrupt destination purge and replacement working.
6. Add User Story 5 $\rightarrow$ Structured telemetry, batch summaries, and dry-run reporting active.
7. Polish $\rightarrow$ Quickstart validation and full regression test suite passing.
