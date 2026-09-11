import json
import logging
import os
import re
import shutil
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from media_cron.config import MediaCronConfig
from media_cron.review.base import ReviewManagerProtocol
from media_cron.review.heuristics import derive_category_hint
from media_cron.review.models import (
    ReviewAction,
    ReviewManifest,
    ReviewStatus,
    UnrecognizedFile,
    UserAnnotation,
)

logger = logging.getLogger(__name__)


class ReviewManager(ReviewManagerProtocol):
    """Manages staging, metadata manifests, and manual triage of unrecognized media."""

    def __init__(self, review_dir: Path):
        self._review_dir = review_dir

    @property
    def review_dir(self) -> Path:
        return self._review_dir

    def list_items(
        self,
        status: ReviewStatus | None = None,
    ) -> list[ReviewManifest]:
        """Lists items in review directory, optionally filtered by status."""
        if not self._review_dir.exists():
            return []

        manifests: list[ReviewManifest] = []
        for entry in sorted(self._review_dir.iterdir()):
            if entry.is_dir() and not entry.name.startswith("."):
                manifest_file = entry / "manifest.json"
                if manifest_file.exists():
                    try:
                        m = ReviewManifest.from_json(manifest_file.read_text(encoding="utf-8"))
                        if status is None or m.status == status:
                            manifests.append(m)
                    except Exception as e:
                        logger.warning("Failed to parse review manifest in %s: %e", entry, e)
        return manifests

    def get_item(self, item_id: str) -> ReviewManifest:
        """Retrieves a specific review manifest by item ID."""
        item_dir = self._review_dir / item_id
        manifest_file = item_dir / "manifest.json"
        if not manifest_file.exists():
            raise FileNotFoundError(f"Review item '{item_id}' not found in {self._review_dir}")
        return ReviewManifest.from_json(manifest_file.read_text(encoding="utf-8"))

    def stage_unrecognized(
        self,
        source_paths: list[Path],
        config: MediaCronConfig,
        failure_reasons: list[str] | None = None,
        seeding_paths: set[Path] | None = None,
        dry_run: bool = False,
    ) -> ReviewManifest:
        """Atomically stages unrecognized files into an isolated subfolder in review_dir."""
        if not source_paths:
            raise ValueError("source_paths cannot be empty")

        staging_dir = config.paths.staging_dir
        # Determine whether files are part of a subfolder release
        is_directory = False
        first_file = source_paths[0]

        try:
            rel_to_staging = first_file.relative_to(staging_dir)
            if len(rel_to_staging.parts) > 1:
                item_name = rel_to_staging.parts[0]
                is_directory = True
                common_root = staging_dir / item_name
            else:
                item_name = first_file.stem
                is_directory = False
                common_root = first_file.parent
        except ValueError:
            item_name = first_file.stem
            is_directory = False
            common_root = first_file.parent

        sanitized_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", item_name).strip("_") or "unrecognized"
        item_id = f"{sanitized_name}_{uuid.uuid4().hex[:8]}"

        files: list[UnrecognizedFile] = []
        total_size = 0
        for p in source_paths:
            if p.exists():
                size = p.stat().st_size
            else:
                size = 0
            rel_path = p.relative_to(common_root) if is_directory else Path(p.name)
            files.append(
                UnrecognizedFile(
                    relative_path=rel_path,
                    size_bytes=size,
                    extension=p.suffix.lower(),
                )
            )
            total_size += size

        category_hint = derive_category_hint(source_paths)
        manifest = ReviewManifest(
            item_id=item_id,
            created_at=datetime.now(UTC),
            original_path=str(item_name),
            is_directory=is_directory,
            total_size_bytes=total_size,
            files=files,
            detected_category_hint=category_hint,
            failure_reasons=list(failure_reasons or []),
            status=ReviewStatus.PENDING,
        )

        if dry_run:
            return manifest

        self._review_dir.mkdir(parents=True, exist_ok=True)
        hidden_staging = self._review_dir / f".staging_{item_id}"
        if hidden_staging.exists():
            shutil.rmtree(hidden_staging)
        hidden_staging.mkdir(parents=True, exist_ok=True)

        mode = config.general.mode.lower()
        normalized_seeds = {p.resolve() for p in (seeding_paths or set())}

        for p in source_paths:
            if not p.exists():
                continue
            rel_path = p.relative_to(common_root) if is_directory else Path(p.name)
            dest_file = hidden_staging / rel_path
            dest_file.parent.mkdir(parents=True, exist_ok=True)

            is_seeding = p.resolve() in normalized_seeds
            if is_seeding:
                # Force non-destructive copy or hardlink
                try:
                    os.link(p, dest_file)
                except OSError:
                    shutil.copy2(p, dest_file)
            elif mode == "move":
                shutil.move(str(p), str(dest_file))
            elif mode == "copy":
                shutil.copy2(p, dest_file)
            else:  # hardlink
                try:
                    os.link(p, dest_file)
                except OSError:
                    shutil.copy2(p, dest_file)

        # Write manifest.json inside hidden staging
        manifest_path = hidden_staging / "manifest.json"
        manifest_path.write_text(manifest.to_json(), encoding="utf-8")

        # Promote atomically
        target_dir = self._review_dir / item_id
        os.replace(hidden_staging, target_dir)

        # Clean up empty directory in staging if moved
        if is_directory and mode == "move" and not is_seeding and common_root.exists():
            try:
                if not any(common_root.iterdir()):
                    common_root.rmdir()
            except OSError:
                pass

        return manifest

    def resolve_item(
        self,
        item_id: str,
        annotation: UserAnnotation,
        action: ReviewAction,
        config: MediaCronConfig,
        dry_run: bool = False,
    ) -> ReviewManifest:
        """Applies a resolution action to a reviewed item."""
        manifest = self.get_item(item_id)
        item_dir = self._review_dir / item_id

        if action == ReviewAction.SKIP:
            return manifest

        if action == ReviewAction.DISCARD:
            manifest.status = ReviewStatus.DISCARDED
            manifest.resolved_at = datetime.now(UTC)
            if annotation:
                manifest.user_annotation = annotation
            if not dry_run:
                shutil.rmtree(item_dir, ignore_errors=True)
            return manifest

        if action == ReviewAction.REINGEST:
            staging_dir = config.paths.staging_dir or (self._review_dir.parent / "staging")
            staging_dir.mkdir(parents=True, exist_ok=True)

            manifest.status = ReviewStatus.REINGESTED
            manifest.resolved_at = datetime.now(UTC)
            manifest.user_annotation = annotation

            if not dry_run:
                for f in manifest.files:
                    src_file = item_dir / f.relative_path
                    dest_file = staging_dir / f.relative_path
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    if src_file.exists():
                        shutil.move(str(src_file), str(dest_file))

                # Write companion sidecar hint
                hint_payload = annotation.to_dict()
                primary_name = manifest.original_path
                hint_file = staging_dir / f"{primary_name}.media-cron-hint.json"
                hint_file.write_text(json.dumps(hint_payload, indent=2), encoding="utf-8")

                shutil.rmtree(item_dir, ignore_errors=True)

            return manifest

        if action == ReviewAction.ORGANIZE_NOW:
            dest_dir = config.paths.destination_dir or Path("/tmp/media")
            manifest.status = ReviewStatus.RESOLVED
            manifest.resolved_at = datetime.now(UTC)
            manifest.user_annotation = annotation

            category = (annotation.category or manifest.detected_category_hint or "movie").lower()
            title = annotation.title or "Unknown Title"
            year = annotation.year
            creator = annotation.creator or "Unknown Creator"
            season = annotation.season or 1
            episode = annotation.episode or 1

            for f in manifest.files:
                ext = f.extension.lstrip(".")
                if category in ("movie", "video_movie"):
                    year_part = f" ({year})" if year else ""
                    rel_dest = f"Movies/{title}{year_part}/{title}{year_part}.{ext}"
                elif category in ("tv", "series", "video_series"):
                    rel_dest = f"TV/{title}/Season {season:02d}/{title} - S{season:02d}E{episode:02d}.{ext}"
                elif category in ("music", "audio_music"):
                    rel_dest = f"Music/{creator}/{title}/{f.relative_path.name}"
                elif category in ("book", "ebook", "book_ebook"):
                    rel_dest = f"Books/{creator}/{title}.{ext}"
                elif category in ("audiobook", "audio_book"):
                    rel_dest = f"Audiobooks/{creator}/{title}/{f.relative_path.name}"
                else:
                    rel_dest = f"Uncategorized/{title}.{ext}"

                dest_file = dest_dir / rel_dest
                if not dry_run:
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    src_file = item_dir / f.relative_path
                    if src_file.exists():
                        shutil.move(str(src_file), str(dest_file))

            if not dry_run:
                shutil.rmtree(item_dir, ignore_errors=True)

                # Media server rescan notification for video categories
                if category in ("movie", "video_movie", "tv", "series", "video_series"):
                    video_cfg = getattr(config, "video", None)
                    if (
                        video_cfg
                        and getattr(video_cfg, "media_server", None)
                        and video_cfg.media_server.enabled
                    ):
                        try:
                            from media_cron.metadata.media_servers import get_media_server_client

                            ms_client = get_media_server_client(video_cfg.media_server.provider)
                            ms_client.trigger_rescan(
                                config=video_cfg.media_server,
                                library_id=video_cfg.media_server.library_id,
                                dry_run=dry_run,
                            )
                        except Exception as e:
                            logger.warning(
                                "Failed to trigger media server rescan for resolved item %s: %s",
                                item_id,
                                e,
                            )

            return manifest

        raise ValueError(f"Unsupported review action: {action}")

    def purge_items(
        self,
        older_than_days: int,
        dry_run: bool = False,
    ) -> list[str]:
        """Purges items in the review directory older than the specified age threshold."""
        if not self._review_dir.exists():
            return []

        cutoff = datetime.now(UTC) - timedelta(days=older_than_days)
        purged_ids: list[str] = []

        for entry in sorted(self._review_dir.iterdir()):
            if entry.is_dir() and not entry.name.startswith("."):
                manifest_file = entry / "manifest.json"
                if manifest_file.exists():
                    try:
                        m = ReviewManifest.from_json(manifest_file.read_text(encoding="utf-8"))
                        if m.created_at < cutoff:
                            purged_ids.append(m.item_id)
                            if not dry_run:
                                shutil.rmtree(entry, ignore_errors=True)
                    except Exception as e:
                        logger.warning("Failed to inspect item in %s during purge: %s", entry, e)

        return purged_ids
