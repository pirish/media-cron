# Feature Specification: Unrecognized Media Staging and Interactive Manual Review

**Feature Branch**: `007-unrecognized-files-staging`  
**Created**: 2026-09-09  
**Status**: Ready  
**Input**: User description: "unrecognized files:  files that can not be identified or cleaned automatically should be staged in a user configurable directory for manual review.  Users should be able to review and add context via interactive cli."

---

## Clarifications & Design Decisions

### Session 2026-09-09
- **Q1: Staging Trigger Policy (FR-005)** → **A**: Automatic whenever `review_dir` is configured. If `paths.review_dir` (or `--review-dir` / `MEDIA_CRON_PATHS_REVIEW_DIR`) is specified, any file that fails all lookup plugins and is not marked as clutter will be automatically staged to the review directory. If unconfigured, unrecognized files remain safely in staging with an informative warning log.
- **Q2: Action After Context Is Added in Interactive CLI (FR-008)** → **A**: Action menu workflow. When reviewing an item in the interactive CLI, the user can supply metadata context and then choose from an action menu:
  - **Organize Now**: Immediately format destination paths and move the files into the final library using the user-provided metadata.
  - **Return to Staging**: Write a companion sidecar metadata hint file (`.media-cron-hint.json`) and move the files back to staging for regular pipeline execution.
  - **Discard**: Delete the unwanted files from the review directory after explicit user confirmation.
  - **Skip**: Leave the item in the review directory for later triage.
- **Q3: Review Directory Storage Layout (FR-009)** → **A**: Isolated item subdirectories with manifest. Each unrecognized item or multi-file release is placed in its own dedicated subdirectory: `<review_dir>/<item_name>_<timestamp_or_uuid>/` containing the original files/hierarchy and a companion `manifest.json` recording failure diagnostic metadata.
- **Q4: Transfer Mode & Torrent Seeding Safety (FR-013)** → **A**: Respect global `general.mode` (move/copy/hardlink), but automatically fallback to non-destructive copy/hardlink if the file is tracked as an active seeding torrent to ensure seed integrity.
- **Q5: Non-Interactive Review Resolution (FR-014)** → **A**: Direct subcommands supported. Alongside the interactive triage session (`media-cron review`), provide direct non-interactive subcommands (`media-cron review resolve <item-id> ...`, `media-cron review discard <item-id>`, `media-cron review reingest <item-id>`) supporting `--format text` and `--format json` for automated scripts and headless operations.
- **Q6: Media Server Rescan on Manual Resolution (FR-015)** → **A**: Automatic rescan notification. When an unrecognized video or music item is resolved with 'Organize Now', the review CLI automatically dispatches a library rescan notification to the configured media server (Jellyfin, Emby, Plex) if media server integration is configured.
- **Q7: Review Item Retention & Purge Policy (FR-016)** → **A**: Manual deletion by default with optional age purge. Unreviewed files are never purged automatically by default (preserving user media safely). A configurable `review.max_age_days` (default 0/disabled) and a `media-cron review purge --older-than <days>` command allow users to clean up stale review items with confirmation.
- **Q8: Category Hint Heuristics (FR-017)** → **A**: Lightweight extension and media heuristics. When staging an unrecognized item, the system analyzes file extensions and basic container cues (.mkv/.mp4/.avi → video, .mp3/.flac/.m4a → music, .epub/.mobi/.pdf → book, .m4b → audiobook) to populate `detected_category_hint` in `manifest.json`, providing a pre-selected default suggestion during interactive review.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Automated Staging of Unrecognized Media into Review Directory (Priority: P1) 🎯 MVP

When media-cron processes the staging directory, any files or release directories that cannot be identified across enabled lookup plugins (books, audiobooks, music, video) or that cannot be cleaned/classified automatically should not remain indefinitely blocking staging or risking lock contention. The pipeline moves these unrecognized items out of active staging into a user-configurable review directory (`paths.review_dir`), preserving bundle cohesion in isolated item subdirectories and recording why the item could not be automatically processed in a companion `manifest.json`.

**Why this priority**: Prevents active staging clutter, eliminates repeated failed processing cycles, and provides a safe holding area so user data is never lost or deleted.

**Independent Test**: Populate staging with files/folders that have unrecognizable names or unsupported metadata. Run media-cron with `--review-dir`. Verify that unrecognized items are relocated to isolated subdirectories in the configured review directory with their companion context preserved, a `manifest.json` is generated for each item, and the batch summary indicates how many items were moved to review.

**Acceptance Scenarios**:
1. **Given** a file or folder in staging that cannot be recognized by any lookup plugin and is not junk clutter, **When** media-cron executes with a configured `review_dir`, **Then** the item is safely relocated from staging into an isolated subdirectory in `review_dir`.
2. **Given** an item moved into `review_dir`, **When** the relocation completes, **Then** a companion `manifest.json` is generated containing failure reasons, original filenames, detection attempts, and ingest timestamps.
3. **Given** a dry-run execution, **When** unrecognized items are encountered, **Then** the plan simulates moving items to the review directory without modifying the filesystem.
4. **Given** no `review_dir` is configured, **When** unrecognized items are encountered, **Then** the files remain in staging untouched and an informative warning is logged.

---

### User Story 2 - Interactive CLI Review and Context Annotation (Priority: P2)

A user running the CLI enters an interactive review mode (`media-cron review`) to inspect all items currently pending in the review directory. The user can view item details (size, sample contents, failure reasons, audio/video stream cues), and provide manual context (media category, title, creator/author/artist, release year, season/episode) through guided prompts.

**Why this priority**: Empowers users to resolve ambiguity that automated heuristics and online lookups could not solve, closing the loop on incomplete metadata.

**Independent Test**: Place an unrecognized item in the review directory. Run the interactive CLI command. Provide title and category context via prompts. Verify that the item's manifest is updated with the user-provided context.

**Acceptance Scenarios**:
1. **Given** items staged in the review directory, **When** the user runs `media-cron review`, **Then** the CLI presents an interactive list of pending review items with clear summary details.
2. **Given** a selected review item, **When** the user enters manual metadata (category, title, year, creator), **Then** the system validates the inputs and attaches them as resolved context in the item manifest.
3. **Given** a non-interactive environment (CI, script, cron), **When** `media-cron review --list` is executed, **Then** items are printed in standard text or `--format json` without hanging on interactive prompts.

---

### User Story 3 - Immediate Resolution, Discard, or Re-ingest Dispatch (Priority: P3)

After a user provides manual context for a review item in the interactive CLI, the user is presented with an action menu allowing them to choose how to apply the resolution: immediately execute organization into the appropriate target library using the enriched metadata, discard/delete the item if it is unwanted, return it to staging with hints, or skip for now.

**Why this priority**: Completes the end-to-end lifecycle so files do not stay trapped in review once the user has clarified their identity.

**Independent Test**: Review an item interactively, provide manual context, and choose "Organize Now". Verify the file is moved directly to the destination library matching the configured template for the chosen category and removed from the review directory.

**Acceptance Scenarios**:
1. **Given** a review item with user-supplied context, **When** the user selects "Organize Now", **Then** the system formats destination paths using the configured templates for that category and transfers the files.
2. **Given** a review item determined to be unwanted junk, **When** the user selects "Discard", **Then** the item is removed from the review directory after confirmation.
3. **Given** a review item where the user wants regular pipeline processing, **When** the user selects "Return to Staging", **Then** the file is moved back to staging with an adjacent sidecar hint file.
4. **Given** a review item the user wishes to defer, **When** the user selects "Skip", **Then** the item remains unchanged in the review directory.

---

### Edge Cases

- **File name collisions in review directory**: Handled via isolated subdirectories with timestamp/UUID suffixes (`<review_dir>/<item_name>_<timestamp_or_uuid>/`), completely preventing collisions.
- **Partial or locked files in staging**: Files currently being written or locked by torrent clients or inotify locks must NOT be treated as unrecognized; they must remain in staging under their normal lock handling.
- **Review directory not configured**: Unrecognized files remain safely in staging with a warning log rather than being dropped or deleted.
- **Empty or abandoned review items**: If an item in review was deleted or moved externally before the CLI reviews it, the CLI gracefully warns and purges orphaned manifests.
- **Seeding torrent safety**: Files linked to active torrent client seeding must respect transfer modes (copy vs hardlink vs move) so active seeds are never broken when staging to review.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a user-configurable review directory path via configuration (`paths.review_dir`), environment variable (`MEDIA_CRON_PATHS_REVIEW_DIR`), and CLI flag (`--review-dir`).
- **FR-002**: The pipeline MUST identify files and folders in staging that cannot be recognized by any configured category lookup plugin (audiobook, book, music, video) and are not marked for deletion by cleaner plugins.
- **FR-003**: The pipeline MUST route unrecognized items into the review directory atomically without risking partial writes or inotify watcher races.
- **FR-004**: Staged review items MUST include a persistent metadata manifest (`manifest.json`) recording the original relative path, failure reason, detection attempts, file size, and ingest timestamps.
- **FR-005**: The pipeline MUST automatically stage unrecognized files to the review directory whenever `paths.review_dir` is configured, without requiring an additional opt-in flag.
- **FR-006**: The system MUST provide an interactive CLI command (`media-cron review`) that displays pending review items and guides the user through inspecting and annotating each item.
- **FR-007**: The interactive CLI MUST allow users to supply manual metadata context including media category (Movie, TV, Music, Book, Audiobook), title, creator/author/artist, year, and season/episode.
- **FR-008**: The interactive CLI MUST provide an action menu allowing the user to select their desired resolution: 'Organize Now' (format and move to final library using supplied context), 'Return to Staging' (move back with sidecar metadata hints for next run), 'Discard' (delete files from review after confirmation), or 'Skip' (leave in review directory for later).
- **FR-009**: The review directory MUST isolate each unrecognized item in its own dedicated subfolder formatted as `<review_dir>/<item_name>_<timestamp_or_uuid>/` containing the original files alongside a companion `manifest.json` metadata manifest to prevent collisions and keep companion assets unified.
- **FR-010**: The review CLI MUST support non-interactive listing and querying via `--format text` and `--format json` for automation and scriptability.
- **FR-011**: In dry-run mode, the pipeline MUST simulate staging unrecognized files to the review directory and report telemetry without modifying files.
- **FR-012**: Execution telemetry and batch summaries MUST report `unrecognized_count` and `review_staged_count`.
- **FR-013**: When staging unrecognized files to the review directory, the system MUST respect the configured transfer mode (`general.mode`), but MUST automatically fallback to non-destructive copy or hardlink when the item is associated with an active torrent seed.
- **FR-014**: The review CLI MUST provide non-interactive resolution subcommands (`resolve`, `discard`, `reingest`) accepting target parameters and flags, supporting both text and JSON outputs for scriptability.
- **FR-015**: When a review item is resolved via 'Organize Now' into a video or music destination library, the system MUST trigger the configured media server library rescan (Jellyfin/Emby/Plex) following existing rescan retry and debouncing contracts.
- **FR-016**: The system MUST keep unreviewed items indefinitely by default without automatic deletion, but MUST support an optional retention setting (`review.max_age_days`) and a dedicated CLI command (`media-cron review purge --older-than <days>`) that requires confirmation in interactive mode or an explicit `--force` flag in non-interactive mode.
- **FR-017**: When generating the review manifest for an unrecognized item, the system MUST derive a suggested `detected_category_hint` based on file extensions and container heuristics, pre-populating this recommendation in the interactive review CLI.

---

### Key Entities *(include if feature involves data)*

- **UnrecognizedItem**: Represents a file or multi-file directory from staging that failed automated identification and cleanup. Contains `item_id`, `source_path`, `staged_path`, `size_bytes`, `detected_category_hint`, `failure_reason`, and `ingest_timestamp`.
- **ReviewManifest**: Persistent JSON metadata file (`manifest.json`) stored alongside the unrecognized item in the review directory. Records original staging path, failure reasons, attempted provider lookups, user-added context annotations, and review status (`pending`, `annotated`, `resolved`, `discarded`).
- **UserAnnotation**: Context provided by the user via interactive CLI, including `target_category`, `title`, `creator`, `year`, `season`, `episode`, and notes.
- **ReviewAction**: An operation applied to a reviewed item: `ORGANIZE_NOW` (immediate library placement), `REINGEST` (move back to staging with sidecar hints), `DISCARD` (delete from review), or `SKIP` (leave in review).

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of files that fail automated identification/cleaning can be isolated from staging into review without data loss.
- **SC-002**: Active torrent seeding files are never corrupted or deleted during review staging.
- **SC-003**: Users can review and resolve an unrecognized item via the interactive CLI in under 30 seconds.
- **SC-004**: The interactive review CLI provides non-interactive JSON export of pending items for headless environments.

---

## Assumptions

- If `paths.review_dir` is not configured, the default behavior is to leave unrecognized files in staging and log a helpful recommendation to configure `review_dir`.
- Interactive prompts will utilize standard terminal input/output and fall back gracefully to non-interactive mode if stdin is not a TTY.
- The review directory resides on a filesystem compatible with atomic directory renames or fallback copies where cross-device moves occur.
- Standard media categories align with media-cron's existing domain models: `movie`, `tv`, `music`, `book`, `audiobook`.
