# Contract: Transfer Verifier Protocol Interface

**Feature Branch**: `011-resume-failed-transfers`
**Date**: 2026-10-15
**Spec Reference**: [spec.md](../spec.md) | **Data Model**: [data-model.md](../data-model.md)

---

## 1. Protocol Definition

The `TransferVerifierProtocol` defines the contract for inspecting existing target candidates, performing fast-rejection and content hashing, safely purging corrupt candidates, and tracking recovery telemetry.

```python
from pathlib import Path
from typing import Protocol, runtime_checkable
from media_cron.recovery.models import VerificationResult, VerificationStatus, RecoverySummary


@runtime_checkable
class TransferVerifierProtocol(Protocol):
    """Contract for verifying candidate file integrity and performing safe restarts."""

    def compute_sha256(self, file_path: Path, chunk_size: int = 1048576) -> str:
        """Computes hexadecimal SHA-256 digest of a local file using streaming chunks.

        Preconditions:
            - file_path exists and is a readable regular file.
        Postconditions:
            - Returns a lowercase 64-character hexadecimal string.
            - Does not hold file descriptors open after completion.
        Raises:
            - FileNotFoundError: If file_path does not exist.
            - PermissionError: If read permissions are lacking.
        """
        ...

    def verify_item(
        self,
        source_path: Path,
        target_path: Path,
    ) -> VerificationResult:
        """Evaluates whether an existing candidate target matches the source payload.

        Handles both single regular files and multi-file release directories.

        Execution Order:
            1. If target does not exist -> VerificationStatus.MISSING
            2. If same inode & device -> VerificationStatus.MATCH (fast hardlink short-circuit)
            3. If file size differs -> VerificationStatus.SIZE_MISMATCH (fast rejection, no hashing)
            4. If multi-file directory -> enumerate all constituent files; check size and hash for each
            5. If sizes match -> compute SHA-256 for source and target; compare digests

        Preconditions:
            - source_path exists and is accessible.
        Postconditions:
            - Returns a populated VerificationResult.
            - If any file fails in a directory, overall_status is MISMATCH.
        """
        ...

    def purge_item(
        self,
        target_path: Path,
        allowed_parent_roots: list[Path],
        dry_run: bool = False,
    ) -> bool:
        """Safely removes an invalid/corrupt candidate file or directory.

        Preconditions:
            - target_path must be strictly contained within at least one path in allowed_parent_roots.
            - target_path must not equal any path in allowed_parent_roots.
            - target_path must not be filesystem root ('/').
        Postconditions:
            - If dry_run is False and target exists: target_path is unlinked (if file)
              or recursively removed (if directory). Returns True if deleted, False if did not exist.
            - If dry_run is True: No filesystem changes occur. Returns True if candidate existed.
        Raises:
            - ValueError: If target_path violates allowed parent root containment boundaries.
            - OSError: If deletion fails due to filesystem permissions or locks.
        """
        ...

    @property
    def summary(self) -> RecoverySummary:
        """Returns the aggregate recovery and verification telemetry for this session."""
        ...
```

---

## 2. Ingestion & Output Plugin Integration Contracts

### Input Plugin Ingestion Hook (`discover`)

When an input plugin (`TorrentInputPlugin`, `DirectoryScannerInputPlugin`) processes a queued item:

```python
# Pseudo-contract inside input plugin
candidate_dest = staging_path / item.name
if candidate_dest.exists():
    result = verifier.verify_item(source_path=item.path, target_path=candidate_dest)
    if result.can_resume:
        logger.info("Resuming staged item '%s' (hash verified, %d bytes saved)", item.name, result.bytes_saved)
        verifier.summary.items_resumed += 1
        verifier.summary.bytes_saved += result.bytes_saved
        # Skip re-copying, yield existing staged item
        yield DiscoveredItem(source_path=candidate_dest, ...)
        continue
    else:
        logger.warning("Corrupt staged candidate '%s' detected (%s); purging and restarting", item.name, result.overall_status.value)
        verifier.purge_item(candidate_dest, allowed_parent_roots=[staging_path], dry_run=dry_run)
        verifier.summary.items_purged += 1

# Proceed with fresh copy to staging
```

---

### Output Organizer Hook (`LibraryOrganizerOutput.execute`)

When `LibraryOrganizerOutput` evaluates target destination path:

```python
if dest.exists():
    result = verifier.verify_item(source_path=src, target_path=dest)
    if result.can_resume:
        logger.info("Destination file '%s' verified matching; bypassing transfer", dest)
        verifier.summary.transfers_bypassed += 1
        verifier.summary.bytes_saved += result.bytes_saved
        return OperationResult(
            plan=plan,
            status=OperationStatus.SUCCESS,
            message=f"Destination file already matches source content hash; transfer bypassed ({result.bytes_saved} bytes saved)",
        )
    else:
        logger.warning(
            "Corrupt destination file '%s' detected; purging before fresh transfer", dest
        )
        verifier.purge_item(dest, allowed_parent_roots=[dest.parent], dry_run=plan.dry_run)
        verifier.summary.items_purged += 1

# Proceed with standard transfer (copy/move/hardlink)
```
