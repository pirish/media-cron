# Implementation Plan: High-Speed OS-Native and Custom Utility File Transfers

**Branch**: `012-native-file-transfers` | **Date**: 2026-11-05 | **Spec**: [spec.md](file:///home/pirish/projects/media-cron/specs/012-native-file-transfers/spec.md)

**Input**: Feature specification from `/specs/012-native-file-transfers/spec.md`

## Summary

Replace slow application-level Python file streaming (`shutil.copy2`, `shutil.copytree`, `shutil.move`) with a centralized `FileTransferExecutor` (`media_cron/transfer/`) supporting three configurable strategies:
1. **`native` (default)**: Delegates copies to `cp -r --reflink=auto` (with automatic retry as `cp -r` when `--reflink` is unsupported by the host `cp` binary) and moves to `mv` for kernel-level throughput and Copy-on-Write clones.
2. **`custom`**: Executes user-defined copy and move command templates (`{src}` / `{dst}` placeholders or positional arguments) tokenized via `shlex.split()` and invoked safely with `subprocess.run(..., shell=False)`, including destination integrity verification and automatic leftover source cleanup on custom moves.
3. **`builtin` (and automatic fallback)**: Uses Python's `shutil` module directly or as an automatic fallback when external utilities are missing or fail—while cleaning up partial destination artifacts before fallback and aborting immediately without fallback on disk-space exhaustion (`ENOSPC`).

Transfer settings are configurable globally (`TransferConfig` in `config.yaml`, `MEDIA_CRON_TRANSFER_*` environment variables, and CLI flags) and overridable per destination endpoint (`DestinationEndpointConfig.transfer`), with per-transfer and batch-level telemetry (`TransferSummary`).

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: Python Standard Library (`subprocess`, `shlex`, `shutil`, `pathlib`, `time`, `errno`, `dataclasses`, `enum`), `typer>=0.12` (CLI options), `pyyaml>=6.0` (YAML config parsing) — zero new third-party dependencies.

**Storage**: Local POSIX filesystems, CoW filesystems (Btrfs, ZFS, XFS), and network-attached storage mounts (NFS, SMB/CIFS, mergerfs).

**Testing**: `pytest>=8.0`, `pytest-cov>=5.0`, `ruff>=0.6.0`

**Target Platform**: Linux / POSIX server and container environments (Docker, Kubernetes, systemd/cron hosts).

**Project Type**: Library + CLI batch media automation service (`media-cron`).

**Performance Goals**: Achieve >=90% of raw OS `cp`/`mv` throughput on large media transfers (>=1 GB) (`SC-001`), eliminating Python user-space stream buffering overhead.

**Constraints**: Zero shell interpolation (`shell=False` mandatory for `SC-002`); configurable subprocess timeout (`timeout_seconds`, default `3600.0`); fast-abort without fallback on `ENOSPC` (`FR-007`); 100% side-effect-free `--dry-run` (`SC-004`).

**Scale/Scope**: 1 new core package (`media_cron/transfer/`), updates to global and routing config models (`media_cron/config.py`, `media_cron/routing/models.py`), CLI flags (`media_cron/cli.py`), batch telemetry (`media_cron/models.py`), and unification across all 8 file-transfer call sites in `media_cron/`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate Assessment | Status |
|-----------|-----------------|--------|
| **I. Library-First & CLI-Driven Architecture** | File transfer logic is encapsulated in a standalone `media_cron/transfer/` package (`TransferExecutorProtocol`, `FileTransferExecutor`, `TransferConfig`) independent of CLI concerns, and exposed via `--transfer-strategy`, `--copy-cmd`, `--move-cmd`, `--no-transfer-fallback`, and `--transfer-timeout` CLI flags with human-readable and `--json-logs` output. | **PASS** |
| **II. Test-Driven Media Classification & Routing (TDD)** | Unit tests (`test_transfer_models.py`, `test_transfer_executor.py`), contract tests (`test_transfer_contracts.py`), and end-to-end integration tests (`test_native_file_transfers.py`) covering special characters, `cp --reflink=auto` retry, custom move cleanup, `ENOSPC` fast-abort, and fallback recovery will be authored prior to implementation. | **PASS** |
| **III. Idempotent & Non-Destructive File Operations** | External utility failures or timeouts purge partial destination artifacts before attempting `builtin` fallback or raising errors. Custom moves verify destination existence and byte size match before deleting leftover source paths. `--dry-run` resolves and logs commands without spawning subprocesses or mutating the filesystem. | **PASS** |
| **IV. Observability & Predictable Cron Execution** | Every transfer logs strategy (`native`, `custom`, `builtin`), fallback warnings (exit code + `stderr`), bytes transferred, duration (ms), and throughput (MB/s). `BatchSummary.transfer_summary` aggregates counts and totals for JSON and text reports. | **PASS** |
| **V. Declarative Configuration & Container-Native Portability** | Configured declaratively via `transfer:` in `config.yaml`, `MEDIA_CRON_TRANSFER_*` environment variables, per-destination route overrides, and CLI flags. Uses only Python stdlib (`subprocess`, `shlex`, `shutil`, `errno`) and standard POSIX `cp`/`mv` with automatic `builtin` fallback for minimal containers. | **PASS** |

*Post-Phase 1 Re-Check*: All Phase 1 artifacts (`research.md`, `data-model.md`, `contracts/transfer-executor-interface.md`, `contracts/config-and-cli-schema.md`, `quickstart.md`) satisfy all five constitutional principles with zero violations.

## Project Structure

### Documentation (this feature)

```text
specs/012-native-file-transfers/
├── plan.md                                    # This file (/speckit-plan command output)
├── research.md                                # Phase 0 output (/speckit-plan command)
├── data-model.md                              # Phase 1 output (/speckit-plan command)
├── quickstart.md                              # Phase 1 output (/speckit-plan command)
├── contracts/                                 # Phase 1 output (/speckit-plan command)
│   ├── transfer-executor-interface.md         # TransferExecutorProtocol & behavioral invariants
│   └── config-and-cli-schema.md               # YAML, env var, CLI flag, and telemetry contracts
└── tasks.md                                   # Phase 2 output (/speckit-tasks command)
```

### Source Code (repository root)

```text
media_cron/
├── config.py                                  # Add TransferConfig parsing (YAML + MEDIA_CRON_TRANSFER_* env vars)
├── cli.py                                     # Add --transfer-strategy, --copy-cmd, --move-cmd, --no-transfer-fallback, --transfer-timeout
├── models.py                                  # Attach TransferSummary to BatchSummary
├── pipeline.py                                # Instantiate FileTransferExecutor & propagate to plugins/spoolers/managers
├── transfer/                                  # NEW: Centralized high-speed file transfer engine
│   ├── __init__.py                            # Public exports
│   ├── models.py                              # TransferStrategy, TransferAction, TransferConfig, TransferOperation, TransferOutcome, TransferSummary, exceptions
│   ├── base.py                                # TransferExecutorProtocol
│   └── executor.py                            # FileTransferExecutor (native cp/mv, custom shlex template, builtin fallback, ENOSPC check, move cleanup)
├── routing/
│   ├── models.py                              # Add optional transfer: TransferConfig | None to DestinationEndpointConfig
│   ├── resolver.py                            # Inherit global TransferConfig defaults for route destination overrides
│   └── engine.py                              # Pass route-level destination.transfer override to FileTransferExecutor
├── plugins/
│   ├── input/
│   │   ├── directory.py                       # Delegate staging move to FileTransferExecutor
│   │   └── torrent.py                         # Delegate staging copy/copytree to FileTransferExecutor
│   └── output/
│       ├── organizer.py                       # Delegate copy, move, and cross-device hardlink fallback to FileTransferExecutor (with route override support)
│       └── seed.py                            # Delegate cross-device hardlink fallback copy to FileTransferExecutor
├── metadata/
│   ├── music_spooler.py                       # Delegate hidden staging copy to FileTransferExecutor
│   ├── video_spooler.py                       # Delegate hidden staging copy to FileTransferExecutor
│   └── converter.py                           # Delegate converted ebook move to FileTransferExecutor
└── review/
    └── manager.py                             # Delegate unrecognized item staging copy/move and resolution move to FileTransferExecutor

tests/
├── contract/
│   └── test_transfer_contracts.py             # Protocol, config/env/CLI precedence, and behavioral invariant tests
├── unit/
│   ├── test_transfer_models.py                # TransferConfig validation, template tokenization, and summary models
│   └── test_transfer_executor.py              # Native cp --reflink=auto retry, mv, custom move source cleanup, ENOSPC abort, timeout & fallback unit tests
└── integration/
    └── test_native_file_transfers.py          # End-to-end pipeline transfers (native, custom with special chars, per-route override, fallback, dry-run)
```

**Structure Decision**: Single-project library + CLI package layout (`media_cron/` and `tests/`). Introducing `media_cron/transfer/` isolates all subprocess/fallback/verification logic behind `TransferExecutorProtocol` while keeping all 8 existing pipeline call sites clean and cohesive.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No constitutional violations. All gates pass without exception.
