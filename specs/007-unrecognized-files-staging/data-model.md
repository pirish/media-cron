# Data Model: Unrecognized Media Staging and Interactive Manual Review

**Feature Branch**: `007-unrecognized-files-staging`
**Date**: 2026-09-09

---

## 1. Domain Enums

### `ReviewStatus`
Lifecycle states of an unrecognized item in the review subsystem:
- `PENDING`: Staged in review directory awaiting manual inspection.
- `RESOLVED`: Successfully organized into the destination library.
- `REINGESTED`: Returned to staging with companion metadata hints for automated pipeline re-processing.
- `DISCARDED`: Deleted from the review directory by explicit user action.

### `ReviewAction`
User-selected resolution actions available in the review CLI:
- `ORGANIZE_NOW`: Immediately format destination paths and move files into the library.
- `REINGEST`: Write `.media-cron-hint.json` and move files back to staging.
- `DISCARD`: Delete the item directory from review after confirmation.
- `SKIP`: Leave the item untouched in the review directory.

---

## 2. Core Entities & Data Structures

### `UnrecognizedFile`
Metadata describing an individual file within an unrecognized item bundle.
- `relative_path`: `Path` (Path relative to the item directory root).
- `size_bytes`: `int` (File size in bytes).
- `extension`: `str` (Normalized lowercase extension, e.g. `.mkv`).

### `UserAnnotation`
User-provided contextual metadata supplied during interactive or non-interactive review.
- `category`: `str` (One of `"movie"`, `"tv"`, `"music"`, `"book"`, `"audiobook"`).
- `title`: `str` (User-verified title).
- `creator`: `str | None` (Artist, author, show director, or band name).
- `year`: `int | None` (Release or publication year).
- `season`: `int | None` (Season number for TV).
- `episode`: `int | None` (Episode number for TV).
- `notes`: `str | None` (Optional user remarks or flags).

### `ReviewManifest`
The complete persistent metadata document saved as `manifest.json` inside each item subdirectory.
- `item_id`: `str` (Unique identifier, e.g. `<sanitized_name>_<timestamp_or_uuid>`).
- `created_at`: `datetime` (ISO 8601 UTC timestamp when staged into review).
- `original_path`: `str` (Original relative path within staging directory).
- `is_directory`: `bool` (True if original release was a multi-file directory).
- `total_size_bytes`: `int` (Cumulative byte count of all files in the item).
- `files`: `list[UnrecognizedFile]` (List of included files).
- `detected_category_hint`: `str | None` (Heuristic category guess, e.g. `"movie"`, `"tv"`, `"music"`, `"book"`, `"audiobook"`).
- `failure_reasons`: `list[str]` (Diagnostic explanations why automated recognition/cleaners failed).
- `status`: `ReviewStatus` (Current review status).
- `user_annotation`: `UserAnnotation | None` (Attached user context once reviewed).
- `resolved_at`: `datetime | None` (Timestamp when resolution action was executed).

---

## 3. Configuration Models

### `PathsConfig` Additions
```python
@dataclass
class PathsConfig:
    # Existing fields...
    source_dir: Path | None = None
    staging_dir: Path | None = None
    destination_dir: Path | None = None
    # Feature 007 addition:
    review_dir: Path | None = None
```

### `ReviewConfig`
```python
@dataclass
class ReviewConfig:
    enabled: bool = True
    max_age_days: int = 0  # 0 indicates indefinite retention (no automatic purge)
```

Attached to `MediaCronConfig`:
```python
@dataclass
class MediaCronConfig:
    # Existing fields...
    review: ReviewConfig = field(default_factory=ReviewConfig)
```

---

## 4. Manifest JSON Schema

Each item folder `<review_dir>/<item_id>/` contains `manifest.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "ReviewManifest",
  "type": "object",
  "required": [
    "item_id",
    "created_at",
    "original_path",
    "is_directory",
    "total_size_bytes",
    "files",
    "status"
  ],
  "properties": {
    "item_id": { "type": "string" },
    "created_at": { "type": "string", "format": "date-time" },
    "original_path": { "type": "string" },
    "is_directory": { "type": "boolean" },
    "total_size_bytes": { "type": "integer", "minimum": 0 },
    "files": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["relative_path", "size_bytes", "extension"],
        "properties": {
          "relative_path": { "type": "string" },
          "size_bytes": { "type": "integer" },
          "extension": { "type": "string" }
        }
      }
    },
    "detected_category_hint": { "type": ["string", "null"] },
    "failure_reasons": {
      "type": "array",
      "items": { "type": "string" }
    },
    "status": {
      "type": "string",
      "enum": ["pending", "resolved", "reingested", "discarded"]
    },
    "user_annotation": {
      "type": ["object", "null"],
      "properties": {
        "category": { "type": "string" },
        "title": { "type": "string" },
        "creator": { "type": ["string", "null"] },
        "year": { "type": ["integer", "null"] },
        "season": { "type": ["integer", "null"] },
        "episode": { "type": ["integer", "null"] },
        "notes": { "type": ["string", "null"] }
      }
    },
    "resolved_at": { "type": ["string", "null"], "format": "date-time" }
  }
}
```

---

## 5. Sidecar Hint Schema (`.media-cron-hint.json`)

When an item is returned to staging via `REINGEST`, this file is written adjacent to the media in staging:

```json
{
  "category": "movie",
  "title": "Dune Part Two",
  "year": 2024,
  "creator": "Denis Villeneuve",
  "season": null,
  "episode": null,
  "reingest_timestamp": "2026-09-09T23:15:00Z"
}
```

---

## 6. Batch Telemetry Integration

In `media_cron/models.py` (`BatchSummary`):
- `unrecognized_count`: `int = 0` (Total unrecognized items identified in current run).
- `review_staged_count`: `int = 0` (Number of unrecognized items successfully moved to `review_dir`).
