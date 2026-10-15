# Implementation Plan: Fast Failure Recovery and Transfer Resumption

**Branch**: `011-resume-failed-transfers` | **Date**: 2026-10-15 | **Spec**: [spec.md](spec.md)

---

## Summary

This feature establishes an automated, fast failure recovery subsystem for `media-cron` that detects existing partial or completed items in staging and destination directories following an interrupted or aborted execution. Rather than unconditionally recopying multi-gigabyte media payloads or failing due to dirty directories, the system employs a three-tier integrity verification pipeline (same-inode check -> $O(1)$ size-comparison fast rejection -> streaming SHA-256 hash comparison). If existing files in staging match the queued source, copying is bypassed and processing resumes immediately. If existing destination files match, transfer writing is bypassed and all remaining post-transfer lifecycle operations (such as torrent client seeding relocation and source cleanup) execute idempotently. Any corrupt, truncated, or mismatched candidates corresponding to active queue items are safely purged and re-transferred from scratch.

---

## Technical Context

**Language/Version**: Python 3.11+ (tested on Python 3.11, 3.12, and 3.13)
**Primary Dependencies**: Python standard library (`hashlib.sha256()`, `shutil`, `pathlib.Path`, `os`, `dataclasses`, `enum`, `typing`). Zero new third-party runtime dependencies.
**Storage**: POSIX local filesystems, container volume mounts, and network shares (SMB/NFS).
**Testing**: `pytest` with strict Test-Driven Development (TDD) — contract tests, unit tests, integration tests, and dry-run validation.
**Target Platform**: Linux server, container-native (Docker, Podman, Kubernetes CronJob).
**Project Type**: Standalone Python library module and CLI cron automation utility.
**Performance Goals**:
- Size mismatch fast rejection in <1ms without disk read overhead (FR-002, FR-006).
- Streaming SHA-256 throughput matching sequential disk read speeds via 1MB buffer chunks.
- Resuming interrupted staging batches reduces intake elapsed duration by >80% on multi-gigabyte assets (SC-003).
- Strict $O(1)$ resident memory overhead (<2MB RAM) during hash calculation regardless of file size.
**Constraints**:
- Adherence to Constitution Principle I: Domain logic isolated in `media_cron/recovery/`, decoupled from schedulers and specific input plugins.
- Adherence to Constitution Principle II (TDD): Contract tests and unit tests implemented and verified failing before domain implementation.
- Adherence to Constitution Principle III: Safe containment boundaries in `purge_item()`; dry-run mode strictly non-destructive.
- Clean directory restart for multi-file releases: If any constituent file fails in staging, the entire item folder is purged and re-copied from scratch (FR-010).
**Scale/Scope**: Verifies single-file and multi-file releases across all intake plugins (`TorrentInputPlugin`, `DirectoryScannerInputPlugin`) and output organizers (`LibraryOrganizerOutput`, `VideoSpoolEngine`).

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked post-Phase 1 design.*

- **Principle I: Library-First & CLI-Driven**: **PASS**. Recovery and integrity verification domain logic is encapsulated in `media_cron/recovery/` (`models.py`, `protocols.py`, `verifier.py`), decoupled from cron execution. Telemetry is exposed via standard CLI summary output and machine-parsable JSON.
- **Principle II: Test-First & Contract Verification (NON-NEGOTIABLE)**: **PASS**. Formal protocol contract defined in `media_cron/recovery/protocols.py` (`TransferVerifierProtocol`) with corresponding contract tests in `tests/contract/test_recovery_contract.py`. TDD cycles will be strictly enforced during implementation.
- **Principle III: Idempotency & Failure Resilience**: **PASS**. Core foundation of this feature. Transforms media-cron from "fail-safe but slow to recover" to "fail-safe and self-healing with fast resume". Multi-file directories are atomic; purges enforce strict safety containment; dry-run mode is verified non-destructive.
- **Principle IV: Structured Observability & Diagnosability**: **PASS**. Structured logging across all verification, resume, and purge events (`DEBUG`, `INFO`, `WARNING`). Batch summary metrics track `items_resumed`, `transfers_bypassed`, `items_purged`, and `bytes_saved`.
- **Principle V: Container-Native & Environment Isolation**: **PASS**. Zero external dependencies. Operates seamlessly across local disks and container volume mounts.

---

## Project Structure

### Documentation (this feature)

```text
specs/011-resume-failed-transfers/
├── plan.md                                      # This implementation plan
├── research.md                                  # Phase 0 architectural & hashing decisions
├── data-model.md                                # Phase 1 domain entities, enums, & state transitions
├── quickstart.md                                # Phase 1 runnable end-to-end validation scenarios
├── checklists/
│   └── requirements.md                          # Specification quality checklist
├── contracts/
│   ├── recovery-protocol.md                     # TransferVerifierProtocol contract & integration hooks
│   └── telemetry-schema.md                      # JSON schema & CLI summary output specification
└── tasks.md                                     # Implementation tasks (generated by /speckit-tasks)
```

### Source Code Layout (repository root)

```text
media_cron/
├── recovery/
│   ├── __init__.py                              # Exports: TransferVerifier, VerificationStatus, RecoverySummary
│   ├── models.py                                # VerificationStatus, FileIntegrityRecord, VerificationResult, RecoverySummary
│   ├── protocols.py                             # TransferVerifierProtocol definition
│   └── verifier.py                              # Streaming SHA-256, size-first check, same-inode check, safe purge
├── models.py                                    # BatchSummary update with recovery_summary
├── pipeline.py                                  # Pipeline recovery coordination & post-transfer lifecycle execution
└── plugins/
    ├── input/
    │   ├── torrent.py                           # Staging candidate verification & resume hook
    │   └── directory.py                         # Directory scanner staging recovery hook
    └── output/
        └── organizer.py                         # Destination target verification & bypass hook

tests/
├── contract/
│   └── test_recovery_contract.py                # TransferVerifierProtocol compliance tests
├── unit/
│   └── recovery/
│       ├── test_recovery_models.py              # Enums, dataclass invariants, and summary serialization
│       ├── test_transfer_verifier.py            # Size-first rejection, same-inode, SHA-256, multi-file verification
│       └── test_safe_purge.py                   # Containment boundary validation, dry-run safety, directory rmtree
└── integration/
    ├── test_staging_recovery_flow.py            # Ingestion scan resume and corrupted candidate purge
    ├── test_destination_bypass_flow.py          # Destination bypass and post-transfer seeding relocation
    └── test_recovery_dry_run.py                 # Dry-run non-destructive verification and telemetry accuracy
```

**Structure Decision**: Domain logic is cleanly isolated in `media_cron/recovery/`, maintaining modular decoupling and enabling exhaustive unit testing without requiring real torrent clients or external media libraries.

---

## Complexity Tracking

*No constitutional violations identified. Design adheres to all five core principles without requiring architectural exemptions.*
