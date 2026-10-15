from __future__ import annotations

import hashlib
import logging
import shutil
from pathlib import Path

from media_cron.recovery.models import (
    FileIntegrityRecord,
    RecoverySummary,
    VerificationResult,
    VerificationStatus,
)

logger = logging.getLogger(__name__)


class TransferVerifier:
    """Evaluates candidate file integrity, rejects size mismatches fast, and safely purges corrupt artifacts."""

    def __init__(self, summary: RecoverySummary | None = None) -> None:
        self._summary = summary if summary is not None else RecoverySummary()

    @property
    def summary(self) -> RecoverySummary:
        return self._summary

    def compute_sha256(self, file_path: Path, chunk_size: int = 1048576) -> str:
        """Computes hexadecimal SHA-256 digest using streaming chunk buffers."""
        file_path = Path(file_path).resolve()
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(chunk_size):
                hasher.update(chunk)
        return hasher.hexdigest()

    def verify_file(self, source_file: Path, target_file: Path) -> FileIntegrityRecord:
        """Verifies a single file candidate against its source file."""
        src = Path(source_file).resolve()
        target = Path(target_file).resolve()
        rel_path = Path(src.name)

        src_stat = src.stat()
        src_size = src_stat.st_size

        if not target.exists():
            return FileIntegrityRecord(
                relative_path=rel_path,
                source_path=src,
                target_path=target,
                source_size=src_size,
                target_size=None,
                source_hash=None,
                target_hash=None,
                status=VerificationStatus.MISSING,
                is_same_inode=False,
            )

        target_stat = target.stat()
        target_size = target_stat.st_size

        # 1. Same-inode check (hardlink short-circuit)
        try:
            if src_stat.st_ino == target_stat.st_ino and src_stat.st_dev == target_stat.st_dev:
                return FileIntegrityRecord(
                    relative_path=rel_path,
                    source_path=src,
                    target_path=target,
                    source_size=src_size,
                    target_size=target_size,
                    source_hash=None,
                    target_hash=None,
                    status=VerificationStatus.MATCH,
                    is_same_inode=True,
                )
        except AttributeError:
            pass

        # 2. Size-first fast rejection (FR-002, FR-006)
        if src_size != target_size:
            logger.warning(
                "Corrupted candidate '%s' rejected by file size (%d != %d); purging and restarting",
                target,
                target_size,
                src_size,
            )
            return FileIntegrityRecord(
                relative_path=rel_path,
                source_path=src,
                target_path=target,
                source_size=src_size,
                target_size=target_size,
                source_hash=None,
                target_hash=None,
                status=VerificationStatus.SIZE_MISMATCH,
                is_same_inode=False,
            )

        # 3. Content hash comparison
        src_hash = self.compute_sha256(src)
        target_hash = self.compute_sha256(target)

        if src_hash == target_hash:
            status = VerificationStatus.MATCH
        else:
            logger.warning(
                "Candidate '%s' SHA-256 mismatch (%s != %s); purging and restarting",
                target,
                target_hash,
                src_hash,
            )
            status = VerificationStatus.HASH_MISMATCH

        return FileIntegrityRecord(
            relative_path=rel_path,
            source_path=src,
            target_path=target,
            source_size=src_size,
            target_size=target_size,
            source_hash=src_hash,
            target_hash=target_hash,
            status=status,
            is_same_inode=False,
        )

    def verify_directory(self, source_dir: Path, target_dir: Path) -> VerificationResult:
        """Recursively verifies all files in a multi-file release bundle."""
        src_root = Path(source_dir).resolve()
        target_root = Path(target_dir).resolve()

        if not target_root.exists():
            return VerificationResult(
                item_name=src_root.name,
                source_root=src_root,
                target_root=target_root,
                is_directory=True,
                overall_status=VerificationStatus.MISSING,
                file_records=[],
                total_source_bytes=0,
                bytes_saved=0,
                can_resume=False,
            )

        # Gather all source files
        source_files = [
            p for p in src_root.rglob("*") if p.is_file() and not p.name.startswith(".")
        ]
        records: list[FileIntegrityRecord] = []
        total_bytes = 0
        all_match = True
        failed_status: VerificationStatus | None = None

        for src_file in source_files:
            rel = src_file.relative_to(src_root)
            target_file = target_root / rel
            rec = self.verify_file(src_file, target_file)
            records.append(rec)
            total_bytes += rec.source_size

            if rec.status != VerificationStatus.MATCH:
                all_match = False
                if failed_status is None:
                    failed_status = rec.status

        # Check if target directory has extraneous files
        target_files = [
            p for p in target_root.rglob("*") if p.is_file() and not p.name.startswith(".")
        ]
        source_rel_set = {f.relative_to(src_root) for f in source_files}
        target_rel_set = {f.relative_to(target_root) for f in target_files}

        if target_rel_set != source_rel_set:
            all_match = False
            if failed_status is None:
                failed_status = VerificationStatus.SIZE_MISMATCH

        overall_status = (
            VerificationStatus.MATCH
            if all_match
            else (failed_status or VerificationStatus.HASH_MISMATCH)
        )

        return VerificationResult(
            item_name=src_root.name,
            source_root=src_root,
            target_root=target_root,
            is_directory=True,
            overall_status=overall_status,
            file_records=records,
            total_source_bytes=total_bytes,
            bytes_saved=total_bytes if overall_status == VerificationStatus.MATCH else 0,
            can_resume=(overall_status == VerificationStatus.MATCH),
        )

    def verify_item(self, source_path: Path, target_path: Path) -> VerificationResult:
        """Evaluates whether an existing candidate target matches source payload."""
        src = Path(source_path).resolve()
        target = Path(target_path).resolve()

        self._summary.items_scanned += 1

        if src.is_dir():
            return self.verify_directory(src, target)

        if not target.exists():
            return VerificationResult(
                item_name=src.name,
                source_root=src,
                target_root=target,
                is_directory=False,
                overall_status=VerificationStatus.MISSING,
                total_source_bytes=src.stat().st_size if src.exists() else 0,
                bytes_saved=0,
                can_resume=False,
            )

        rec = self.verify_file(src, target)
        can_resume = rec.status == VerificationStatus.MATCH
        bytes_saved = rec.source_size if can_resume else 0

        return VerificationResult(
            item_name=src.name,
            source_root=src,
            target_root=target,
            is_directory=False,
            overall_status=rec.status,
            file_records=[rec],
            total_source_bytes=rec.source_size,
            bytes_saved=bytes_saved,
            can_resume=can_resume,
        )

    def purge_item(
        self,
        target_path: Path,
        allowed_parent_roots: list[Path],
        dry_run: bool = False,
    ) -> bool:
        """Safely removes an invalid or corrupt candidate file or directory."""
        target = Path(target_path).resolve()

        if target == Path("/"):
            raise ValueError("Cannot purge root directory")

        is_contained = False
        for parent_root in allowed_parent_roots:
            resolved_root = Path(parent_root).resolve()
            if target == resolved_root:
                raise ValueError(f"Cannot purge an allowed parent root itself: {target}")
            try:
                target.relative_to(resolved_root)
                is_contained = True
                break
            except ValueError:
                continue

        if not is_contained:
            raise ValueError(
                f"Target path {target} violates boundary containment; not within allowed roots {allowed_parent_roots}"
            )

        if not target.exists():
            return False

        if dry_run:
            logger.info("[DRY-RUN] Would purge corrupt candidate '%s'", target)
            return True

        logger.info("Purged invalid candidate '%s' prior to clean restart", target)
        try:
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
            return True
        except Exception as e:
            self._summary.purge_errors += 1
            logger.error("Failed to purge candidate '%s': %s", target, e)
            raise
