# Quickstart Validation Guide: Unrecognized Media Staging & Manual Review

**Feature Branch**: `007-unrecognized-files-staging`  
**Date**: 2026-09-09  

This guide provides 5 runnable end-to-end scenarios demonstrating the complete lifecycle of unrecognized media staging, metadata manifest generation, interactive triage, non-interactive resolution, and media server notifications.

---

## Prerequisites

- Active virtual environment with dependencies installed:
  ```bash
  source .venv/bin/activate
  ```
- Staging, review, and destination library directories created:
  ```bash
  mkdir -p /tmp/mc_test/staging /tmp/mc_test/review /tmp/mc_test/dest/{Movies,TV,Music,Books}
  ```

---

## Scenario 1: Automated Staging of Unrecognized File into Review Directory

**Objective**: Verify that an unrecognized media file that fails all lookup plugins is automatically relocated into the review directory with a companion `manifest.json` and category hint.

1. Create an unrecognized video file in staging:
   ```bash
   echo "sample content" > /tmp/mc_test/staging/Unknown_obscure_video.mkv
   ```

2. Execute media-cron with `--review-dir`:
   ```bash
   media-cron process \
     --source-dir /tmp/mc_test/staging \
     --staging-dir /tmp/mc_test/staging \
     --destination-dir /tmp/mc_test/dest \
     --review-dir /tmp/mc_test/review
   ```

3. **Validation**:
   - `/tmp/mc_test/staging/Unknown_obscure_video.mkv` no longer exists in staging.
   - Review directory contains an isolated subfolder, e.g. `/tmp/mc_test/review/Unknown_obscure_video_*/`.
   - `manifest.json` exists in that subfolder with `status = "pending"` and `detected_category_hint = "movie"`.

---

## Scenario 2: Non-Interactive Inspection (`review list` & `review show`)

**Objective**: Verify that pending review items can be listed and inspected in both text and JSON formats without interactive prompts.

1. List pending items in text format:
   ```bash
   media-cron review list --review-dir /tmp/mc_test/review
   ```
   **Output**: Formatted table showing Item ID, Name, Size, Category Hint, and Status.

2. Export pending items as JSON:
   ```bash
   media-cron review list --review-dir /tmp/mc_test/review --format json
   ```
   **Output**: Valid JSON array containing full `ReviewManifest` structures.

3. Show item details:
   ```bash
   ITEM_ID=$(media-cron review list --review-dir /tmp/mc_test/review --format json | jq -r '.[0].item_id')
   media-cron review show "$ITEM_ID" --review-dir /tmp/mc_test/review
   ```

---

## Scenario 3: Non-Interactive Direct Organization (`review resolve --action organize`)

**Objective**: Apply manual metadata to an unrecognized item and immediately organize it into the target library.

1. Execute non-interactive resolution:
   ```bash
   media-cron review resolve "$ITEM_ID" \
     --review-dir /tmp/mc_test/review \
     --category movie \
     --title "Solaris" \
     --year 1972 \
     --action organize
   ```

2. **Validation**:
   - The movie is organized at `/tmp/mc_test/dest/Movies/Solaris (1972)/Solaris (1972).mkv`.
   - The item in `/tmp/mc_test/review/` is marked `status = "resolved"` (or removed).
   - If media server was configured, a rescan request was dispatched.

---

## Scenario 4: Non-Interactive Re-Ingest to Staging (`review resolve --action reingest`)

**Objective**: Annotate an item and return it to staging with a `.media-cron-hint.json` sidecar for regular cron pipeline execution.

1. Place an unrecognized book file in review directory:
   ```bash
   mkdir -p /tmp/mc_test/review/custom_notes_123
   echo "notes content" > /tmp/mc_test/review/custom_notes_123/notes.epub
   cat << 'EOF' > /tmp/mc_test/review/custom_notes_123/manifest.json
   {
     "item_id": "custom_notes_123",
     "created_at": "2026-09-09T23:00:00Z",
     "original_path": "notes.epub",
     "is_directory": false,
     "total_size_bytes": 13,
     "files": [{"relative_path": "notes.epub", "size_bytes": 13, "extension": ".epub"}],
     "detected_category_hint": "book",
     "failure_reasons": ["No author found"],
     "status": "pending"
   }
   EOF
   ```

2. Resolve with re-ingest action:
   ```bash
   media-cron review resolve "custom_notes_123" \
     --review-dir /tmp/mc_test/review \
     --category book \
     --title "Design Patterns" \
     --creator "Gang of Four" \
     --year 1994 \
     --action reingest
   ```

3. **Validation**:
   - Files are moved back to `/tmp/mc_test/staging/notes.epub`.
   - Companion hint `/tmp/mc_test/staging/notes.epub.media-cron-hint.json` exists containing the user metadata.

---

## Scenario 5: Discard and Retention Purge

**Objective**: Verify safe deletion of unwanted review items and batch purging of expired items.

1. Discard an unwanted item:
   ```bash
   media-cron review discard "$ITEM_ID" --review-dir /tmp/mc_test/review --force
   ```
   **Validation**: Item folder is removed from `/tmp/mc_test/review/`.

2. Purge stale items:
   ```bash
   media-cron review purge --older-than 7 --review-dir /tmp/mc_test/review --force
   ```
   **Validation**: Reports count of purged items older than 7 days.
