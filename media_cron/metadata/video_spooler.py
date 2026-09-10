from __future__ import annotations

import os
import shutil
import subprocess
import uuid
from pathlib import Path

from media_cron.metadata.models import VideoReleaseBundle, VideoSpoolResult


class VideoSpoolEngine:
    """Deposits video release bundles atomically into external video manager drop folders."""

    def stage_bundle(
        self,
        bundle: VideoReleaseBundle,
        spool_dir: Path,
        dry_run: bool = False,
    ) -> Path:
        """Transfers all primary videos and companion assets into a hidden temporary staging folder."""
        folder_name = bundle.root_path.name
        staging_dir = spool_dir / f".incoming_{folder_name}_{uuid.uuid4().hex[:8]}"

        if dry_run:
            return staging_dir

        staging_dir.mkdir(parents=True, exist_ok=True)
        root = bundle.root_path

        try:
            # Transfer primary videos
            for track in bundle.primary_videos:
                try:
                    rel_path = track.path.relative_to(root)
                except ValueError:
                    rel_path = Path(track.path.name)

                dest_file = staging_dir / rel_path
                dest_file.parent.mkdir(parents=True, exist_ok=True)

                self._transfer_file(track.path, dest_file)

            # Transfer companion assets
            for companion in bundle.companion_assets:
                try:
                    rel_path = companion.path.relative_to(root)
                except ValueError:
                    rel_path = Path(companion.path.name)

                dest_file = staging_dir / rel_path
                dest_file.parent.mkdir(parents=True, exist_ok=True)

                self._transfer_file(companion.path, dest_file)

            return staging_dir
        except Exception:
            if staging_dir.exists():
                shutil.rmtree(staging_dir, ignore_errors=True)
            raise

    def _transfer_file(self, src: Path, dest: Path) -> str:
        """Attempts hardlink transfer, falling back to copy if cross-device or unsupported."""
        try:
            os.link(src, dest)
            return "hardlink"
        except OSError:
            shutil.copy2(src, dest)
            return "copy"

    def promote_bundle(
        self,
        staging_dir: Path,
        final_dir: Path,
        dry_run: bool = False,
    ) -> Path | None:
        """Atomically renames the hidden staging folder to the final release destination path.

        Returns None if skipped due to collision.
        """
        if final_dir.exists():
            if staging_dir.exists():
                shutil.rmtree(staging_dir, ignore_errors=True)
            return None

        if dry_run:
            return final_dir

        final_dir.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staging_dir, final_dir)
        return final_dir

    def execute_post_command(
        self,
        command_template: str,
        release_path: Path,
        timeout_seconds: int = 120,
    ) -> tuple[int, str]:
        """Executes a configured post-ingest command hook."""
        cmd = command_template.format(release_path=str(release_path))
        try:
            res = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            output = (res.stdout or "") + (res.stderr or "")
            return res.returncode, output.strip()
        except subprocess.TimeoutExpired:
            return 124, f"Post-ingest command timed out after {timeout_seconds}s"
        except Exception as e:
            return 1, f"Failed to execute post-ingest command: {e}"

    def spool_release(
        self,
        bundle: VideoReleaseBundle,
        spool_dir: Path,
        post_command: str | None = None,
        dry_run: bool = False,
    ) -> VideoSpoolResult:
        """Coordinates staging, promotion, and optional post-ingest command hook."""
        target_dir = spool_dir / bundle.root_path.name
        file_count = len(bundle.primary_videos) + len(bundle.companion_assets)
        bytes_transferred = sum(t.file_size for t in bundle.primary_videos) + sum(
            c.file_size for c in bundle.companion_assets
        )

        if target_dir.exists():
            return VideoSpoolResult(
                bundle_id=bundle.bundle_id,
                source_dir=bundle.root_path,
                target_dir=target_dir,
                file_count=file_count,
                bytes_transferred=0,
                mode="skipped",
                success=True,
                skipped=True,
                skip_reason=f"Target directory '{target_dir.name}' already exists in spool folder",
                post_command_executed=False,
            )

        if dry_run:
            return VideoSpoolResult(
                bundle_id=bundle.bundle_id,
                source_dir=bundle.root_path,
                target_dir=target_dir,
                file_count=file_count,
                bytes_transferred=bytes_transferred,
                mode="dry_run",
                success=True,
                skipped=False,
                post_command_executed=False,
            )

        staging_dir: Path | None = None
        try:
            staging_dir = self.stage_bundle(bundle, spool_dir, dry_run=False)
            final_dir = self.promote_bundle(staging_dir, target_dir, dry_run=False)

            if final_dir is None:
                return VideoSpoolResult(
                    bundle_id=bundle.bundle_id,
                    source_dir=bundle.root_path,
                    target_dir=target_dir,
                    file_count=file_count,
                    bytes_transferred=0,
                    mode="skipped",
                    success=True,
                    skipped=True,
                    skip_reason=f"Target directory '{target_dir.name}' already exists in spool folder",
                    post_command_executed=False,
                )

            post_executed = False
            post_exit_code: int | None = None
            if post_command:
                post_exit_code, _ = self.execute_post_command(post_command, final_dir)
                post_executed = True

            return VideoSpoolResult(
                bundle_id=bundle.bundle_id,
                source_dir=bundle.root_path,
                target_dir=final_dir,
                file_count=file_count,
                bytes_transferred=bytes_transferred,
                mode="hardlink",
                success=True,
                skipped=False,
                post_command_executed=post_executed,
                post_command_exit_code=post_exit_code,
            )
        except Exception as err:
            if staging_dir and staging_dir.exists():
                shutil.rmtree(staging_dir, ignore_errors=True)
            return VideoSpoolResult(
                bundle_id=bundle.bundle_id,
                source_dir=bundle.root_path,
                target_dir=target_dir,
                file_count=file_count,
                bytes_transferred=0,
                mode="failed",
                success=False,
                skipped=False,
                error=str(err),
            )
