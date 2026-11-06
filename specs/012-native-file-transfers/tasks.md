---
description: "Task list for High-Speed OS-Native and Custom Utility File Transfers"
---

# Tasks: High-Speed OS-Native and Custom Utility File Transfers

**Input**: Design documents from `/specs/012-native-file-transfers/`

**Prerequisites**: [plan.md](file:///home/pirish/projects/media-cron/specs/012-native-file-transfers/plan.md) (required), [spec.md](file:///home/pirish/projects/media-cron/specs/012-native-file-transfers/spec.md) (required for user stories), [research.md](file:///home/pirish/projects/media-cron/specs/012-native-file-transfers/research.md), [data-model.md](file:///home/pirish/projects/media-cron/specs/012-native-file-transfers/data-model.md), [contracts/](file:///home/pirish/projects/media-cron/specs/012-native-file-transfers/contracts/), [quickstart.md](file:///home/pirish/projects/media-cron/specs/012-native-file-transfers/quickstart.md)

**Tests**: Included per Constitution Principle II (Test-First & Contract Verification is NON-NEGOTIABLE).

**Organization**: Tasks are grouped by user story (`US1`–`US4`) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (`[US1]`, `[US2]`, `[US3]`, `[US4]`)
- Exact file paths are included in every task description

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the `media_cron/transfer/` package skeleton and test module placeholders.

- [X] T001 Create package directory and public exports placeholder in `media_cron/transfer/__init__.py`
- [X] T002 [P] Create unit, contract, and integration test placeholders in `tests/unit/test_transfer_models.py`, `tests/unit/test_transfer_executor.py`, `tests/contract/test_transfer_contracts.py`, and `tests/integration/test_native_file_transfers.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core transfer data models, exceptions, protocol definition, and configuration schema required by all user stories.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T003 Write unit tests for `TransferStrategy`, `TransferAction`, `TransferConfig`, `TransferOperation`, `TransferOutcome`, `TransferSummary`, and domain exceptions (`TransferError`, `TransferConfigError`, `TransferDiskFullError`, `TransferTimeoutError`, `TransferExecutionError`) in `tests/unit/test_transfer_models.py`
- [X] T004 Implement `TransferStrategy`, `TransferAction`, `TransferConfig`, `TransferOperation`, `TransferOutcome`, `TransferSummary`, and domain exceptions in `media_cron/transfer/models.py`
- [X] T005 [P] Define `TransferExecutorProtocol` (`config`, `copy`, `move`, `get_summary`) in `media_cron/transfer/base.py` and export public symbols in `media_cron/transfer/__init__.py`
- [X] T006 [P] Add `transfer: TransferConfig` field to `MediaCronConfig` with YAML (`transfer:` section) and `MEDIA_CRON_TRANSFER_*` environment variable parsing in `media_cron/config.py`
- [X] T007 [P] Add `transfer_summary: TransferSummary | None = None` field to `BatchSummary` in `media_cron/models.py`

**Checkpoint**: Foundation ready — user story implementation can now begin.

---

## Phase 3: User Story 1 - Accelerated File Transfers via OS-Native Utilities (Priority: P1) 🎯 MVP

**Goal**: Execute file and directory copy/move operations across the pipeline using OS-native utilities (`cp -r --reflink=auto` with automatic retry to `cp -r` when `--reflink` is unsupported, and `mv`) as the default strategy, while preserving 100% side-effect-free `--dry-run` behavior.

**Independent Test**: Run a media copy or move operation using `TransferStrategy.NATIVE`. Verify `cp -r --reflink=auto` (or `cp -r` retry) and `mv` are invoked with `shell=False`, files/directories are transferred intact, parent directories are ensured before execution, and `--dry-run` logs planned commands without modifying disk state.

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST and verify they FAIL before implementation.**

- [X] T008 [P] [US1] Write unit tests for `FileTransferExecutor` native `cp -r --reflink=auto` copy, automatic retry as `cp -r` on unsupported `--reflink` option, native `mv` move, parent directory creation, and `dry_run` simulation in `tests/unit/test_transfer_executor.py`
- [X] T009 [P] [US1] Write contract tests verifying `TransferExecutorProtocol` compliance, `shell=False` invariant, and dry-run non-mutation invariant in `tests/contract/test_transfer_contracts.py`
- [X] T010 [P] [US1] Write end-to-end integration tests for native `cp` and `mv` pipeline execution across staging, organization, seed, spoolers, converter, and review manager in `tests/integration/test_native_file_transfers.py`

### Implementation for User Story 1

- [X] T011 [US1] Implement `FileTransferExecutor` core `native` (`cp -r --reflink=auto` with `cp -r` fallback retry, `mv`) and `builtin` (`shutil.copy2`, `shutil.copytree`, `shutil.move`) execution paths, parent directory assurance, and `dry_run` handling in `media_cron/transfer/executor.py`
- [X] T012 [P] [US1] Delegate staging file/directory move operations to `FileTransferExecutor` in `media_cron/plugins/input/directory.py`
- [X] T013 [P] [US1] Delegate staging file/directory copy operations to `FileTransferExecutor` in `media_cron/plugins/input/torrent.py`
- [X] T014 [P] [US1] Delegate library `copy`, `move`, and cross-device (`EXDEV`) `hardlink` fallback copy operations to `FileTransferExecutor` in `media_cron/plugins/output/organizer.py`
- [X] T015 [P] [US1] Delegate cross-device (`EXDEV`) `hardlink` fallback copy operations to `FileTransferExecutor` in `media_cron/plugins/output/seed.py`
- [X] T016 [P] [US1] Delegate hidden staging copy operations to `FileTransferExecutor` in `media_cron/metadata/music_spooler.py` and `media_cron/metadata/video_spooler.py`
- [X] T017 [P] [US1] Delegate converted ebook move operations to `FileTransferExecutor` in `media_cron/metadata/converter.py`
- [X] T018 [P] [US1] Delegate unrecognized item staging copy/move and review resolution move operations to `FileTransferExecutor` in `media_cron/review/manager.py`
- [X] T019 [US1] Wire `FileTransferExecutor` initialization into `Pipeline` and propagate it to input/output plugins, routing engine, spoolers, and review manager in `media_cron/pipeline.py` and `media_cron/routing/engine.py`

**Checkpoint**: User Story 1 is complete and independently testable as the MVP.

---

## Phase 4: User Story 2 - User-Specified Custom Transfer Utilities (Priority: P2)

**Goal**: Enable operators to configure custom copy and move commands globally (via `config.yaml`, `MEDIA_CRON_TRANSFER_*` env vars, or CLI flags) and per destination route (`routes.<type>.destination.transfer`), safely handling filenames with spaces/quotes/metacharacters via `shlex.split` (`shell=False`) and verifying/cleaning up remaining source paths after custom moves.

**Independent Test**: Configure a custom copy and move command template with `{src}` / `{dst}` placeholders (and positional mode), run transfers on paths containing spaces, quotes, brackets, and ampersands, verify discrete argument invocation, verify custom move source cleanup after destination size check, and verify per-route transfer overrides.

### Tests for User Story 2 ⚠️

- [X] T020 [P] [US2] Write unit tests for `shlex.split` custom template tokenization (`{src}`/`{dst}` placeholders and positional append), special/unicode filename safety, and custom move destination verification + leftover source cleanup in `tests/unit/test_transfer_executor.py`
- [X] T021 [P] [US2] Write contract tests for config/env/CLI precedence (`--transfer-strategy`, `--copy-cmd`, `--move-cmd`, `--no-transfer-fallback`, `--transfer-timeout`) and per-destination endpoint `transfer` override inheritance in `tests/contract/test_transfer_contracts.py`
- [X] T022 [P] [US2] Write integration tests for custom transfer commands with shell metacharacters and per-route destination overrides in `tests/integration/test_native_file_transfers.py`

### Implementation for User Story 2

- [X] T023 [US2] Implement custom command template tokenization (`shlex.split`, `{src}`/`{dst}` replacement, positional append) and custom move destination existence/byte-size verification with automatic leftover source removal in `media_cron/transfer/executor.py`
- [X] T024 [P] [US2] Add optional `transfer: TransferConfig | None = None` override field to `DestinationEndpointConfig` in `media_cron/routing/models.py` and parse route-level `destination.transfer` blocks with global inheritance in `media_cron/config.py` and `media_cron/routing/resolver.py`
- [X] T025 [US2] Pass route-level `destination_endpoint.transfer` as `override_config` to `FileTransferExecutor` during route organization in `media_cron/routing/engine.py` and `media_cron/plugins/output/organizer.py`
- [X] T026 [US2] Add `--transfer-strategy`, `--copy-cmd`, `--move-cmd`, `--no-transfer-fallback`, and `--transfer-timeout` CLI options to `run` (and relevant batch commands) in `media_cron/cli.py`

**Checkpoint**: User Stories 1 and 2 work independently and together.

---

## Phase 5: User Story 3 - Automatic Fallback to Built-In File Transfer (Priority: P3)

**Goal**: Automatically recover from missing binaries, unsupported flags, non-zero exit codes, or command timeouts by cleaning up partial destination artifacts and retrying via Python `builtin` (`shutil`) when `fallback_enabled=True`—while fast-aborting immediately without fallback on insufficient destination disk space (`ENOSPC`).

**Independent Test**: Simulate a missing custom command, a failing command creating a partial destination file, a hung command exceeding `timeout_seconds`, and an `ENOSPC` disk-full error. Verify partial artifacts are always purged, non-`ENOSPC` failures fall back to `builtin` (unless `fallback_enabled=False`), and `ENOSPC` aborts immediately without attempting `builtin` fallback.

### Tests for User Story 3 ⚠️

- [X] T027 [P] [US3] Write unit tests for missing binary fallback, non-zero exit partial artifact cleanup + fallback, `subprocess.TimeoutExpired` termination + cleanup + fallback, strict mode (`fallback_enabled=False`), and `ENOSPC` pre-check / stderr detection fast-abort without fallback in `tests/unit/test_transfer_executor.py`
- [X] T028 [P] [US3] Write integration tests for end-to-end pipeline fallback recovery and `ENOSPC` fast-abort behavior in `tests/integration/test_native_file_transfers.py`

### Implementation for User Story 3

- [X] T029 [US3] Implement pre-flight `shutil.disk_usage` and post-failure `errno.ENOSPC` / `"No space left on device"` stderr inspection to purge partial destination artifacts and raise `TransferDiskFullError` without attempting `builtin` fallback in `media_cron/transfer/executor.py`
- [X] T030 [US3] Implement partial destination artifact cleanup (`_cleanup_partial`), subprocess timeout handling (`timeout_seconds`), warning log emission, and automatic `builtin` (`shutil`) retry when `fallback_enabled=True` in `media_cron/transfer/executor.py`

**Checkpoint**: User Stories 1, 2, and 3 are complete and independently verified.

---

## Phase 6: User Story 4 - Transfer Strategy Observability and Telemetry (Priority: P4)

**Goal**: Emit structured per-transfer logs (effective strategy, bytes transferred, duration in ms, throughput in MB/s, fallback warning reason) and aggregate batch-level transfer metrics (`TransferSummary`) in both human-readable text summaries and JSON output.

**Independent Test**: Run a batch containing both `native` transfers and a `builtin` fallback. Inspect structured logs and `BatchSummary` output (text and JSON) to verify `native_count`, `custom_count`, `builtin_count`, `fallback_count`, `total_bytes_transferred`, and `total_duration_ms`.

### Tests for User Story 4 ⚠️

- [X] T031 [P] [US4] Write unit tests for `FileTransferExecutor.get_summary()` metric aggregation, throughput calculation (`throughput_mbps`), and structured log emission in `tests/unit/test_transfer_executor.py`
- [X] T032 [P] [US4] Write integration tests verifying `BatchSummary.transfer_summary` in pipeline output and CLI text/JSON summary rendering in `tests/integration/test_native_file_transfers.py`

### Implementation for User Story 4

- [X] T033 [US4] Implement per-operation structured logging (strategy, bytes, duration_ms, throughput_mbps, fallback reason) and `TransferSummary` counter aggregation in `media_cron/transfer/executor.py`
- [X] T034 [US4] Attach `transfer_executor.get_summary()` to `BatchSummary.transfer_summary` in `media_cron/pipeline.py` and render transfer telemetry in `render_text_summary()` and JSON summary serialization in `media_cron/cli.py`

**Checkpoint**: All 4 user stories (`US1`–`US4`) are complete and independently testable.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation updates, full test suite validation, and code quality checks across the repository.

- [X] T035 [P] Document `transfer:` configuration, `MEDIA_CRON_TRANSFER_*` environment variables, per-route overrides, and CLI transfer flags in `README.md`
- [X] T036 Run `ruff check .`, `ruff format --check .`, and full `pytest` suite to validate all quickstart scenarios and ensure zero regressions across the codebase

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1: Setup (`T001`–`T002`)**: No dependencies — starts immediately.
- **Phase 2: Foundational (`T003`–`T007`)**: Depends on Phase 1 — **BLOCKS** all user stories (`US1`–`US4`).
- **Phase 3: User Story 1 (`T008`–`T019`, P1 MVP)**: Depends on Phase 2. Establishes `FileTransferExecutor` and wires all 8 pipeline call sites.
- **Phase 4: User Story 2 (`T020`–`T026`, P2)**: Depends on Phase 2 (and extends `FileTransferExecutor` from `US1`).
- **Phase 5: User Story 3 (`T027`–`T030`, P3)**: Depends on Phase 2 and `FileTransferExecutor` from `US1`.
- **Phase 6: User Story 4 (`T031`–`T034`, P4)**: Depends on Phase 2 and `FileTransferExecutor` from `US1`–`US3`.
- **Phase 7: Polish (`T035`–`T036`)**: Depends on completion of `US1`–`US4`.

### User Story Dependency Graph

```text
Phase 1 (Setup)
   │
   ▼
Phase 2 (Foundational: TransferConfig, Models, Protocol)
   │
   ▼
Phase 3: US1 (P1 MVP - OS-Native cp/mv & Pipeline Call-Site Unification)
   ├──► Phase 4: US2 (P2 - Custom Commands, Shell-Safe Tokenization, Route Overrides & CLI Flags)
   ├──► Phase 5: US3 (P3 - Built-In Fallback, Partial Cleanup & ENOSPC Fast-Abort)
   └──► Phase 6: US4 (P4 - Structured Transfer Telemetry & BatchSummary Reporting)
           │
           ▼
Phase 7 (Polish, Docs & Full Regression Suite)
```

---

## Parallel Execution Examples

### User Story 1 (MVP) Parallel Opportunities
```bash
# 1. Write all US1 tests in parallel across distinct test files:
Task T008: "Write unit tests for FileTransferExecutor in tests/unit/test_transfer_executor.py"
Task T009: "Write contract tests in tests/contract/test_transfer_contracts.py"
Task T010: "Write integration tests in tests/integration/test_native_file_transfers.py"

# 2. After T011 (FileTransferExecutor implementation), update all 8 call sites in parallel:
Task T012: "Update media_cron/plugins/input/directory.py"
Task T013: "Update media_cron/plugins/input/torrent.py"
Task T014: "Update media_cron/plugins/output/organizer.py"
Task T015: "Update media_cron/plugins/output/seed.py"
Task T016: "Update media_cron/metadata/music_spooler.py and video_spooler.py"
Task T017: "Update media_cron/metadata/converter.py"
Task T018: "Update media_cron/review/manager.py"
```

### User Story 2 Parallel Opportunities
```bash
# Write US2 tests in parallel:
Task T020: "Unit tests for custom templates & move cleanup in tests/unit/test_transfer_executor.py"
Task T021: "Contract tests for CLI/env/config precedence in tests/contract/test_transfer_contracts.py"
Task T022: "Integration tests for custom commands & route overrides in tests/integration/test_native_file_transfers.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)
1. Complete **Phase 1: Setup** (`T001`–`T002`).
2. Complete **Phase 2: Foundational** (`T003`–`T007`).
3. Complete **Phase 3: User Story 1** (`T008`–`T019`).
4. **STOP and VALIDATE**: Verify native `cp -r --reflink=auto` and `mv` acceleration works end-to-end across all pipeline stages and `--dry-run` is side-effect-free.

### Incremental Delivery
1. **Foundation + US1 (P1)**: Native `cp`/`mv` transfer engine integrated across all 8 pipeline components.
2. **+ US2 (P2)**: Custom user commands (`rsync`, `rclone`, etc.), `{src}`/`{dst}` template tokenization, custom move cleanup verification, per-route overrides, and CLI flags.
3. **+ US3 (P3)**: Automatic `builtin` fallback, partial destination cleanup, timeout protection, and `ENOSPC` fast-abort.
4. **+ US4 (P4)**: Per-transfer throughput telemetry and batch summary reporting.
