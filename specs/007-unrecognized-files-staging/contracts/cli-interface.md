# Contract: CLI Interface Specification

**Subcommand**: `media-cron review`
**Module**: `media_cron.cli`

---

## 1. Subcommands Overview

| Command | Mode | Description |
|---|---|---|
| `media-cron review` | Interactive | Starts an interactive guided review session of all pending items. |
| `media-cron review list` | Non-interactive | Lists pending (or filtered) review items in text or JSON. |
| `media-cron review show <item_id>` | Non-interactive | Displays detailed manifest and file listing for a specific item. |
| `media-cron review resolve <item_id>` | Non-interactive | Directly applies manual metadata and executes an action. |
| `media-cron review discard <item_id>` | Non-interactive | Deletes an item from the review directory (requires `--force` if non-interactive). |
| `media-cron review purge` | Non-interactive | Purges items older than a specified number of days. |

---

## 2. Command Details & Signatures

### `media-cron review`
Interactive triage loop for terminals.
- **Preconditions**: `sys.stdin.isatty()` must be `True`. If not a TTY, prints error and exits with code 1.
- **Workflow**:
  1. Displays pending item count and list.
  2. For each item:
     - Shows filename, size, detected category hint, and failure reason.
     - Prompts for category (pre-fills detected hint if available).
     - Prompts for Title (required), Creator/Artist/Author (optional), Year (optional), Season/Episode (if TV).
     - Presents Action Menu: `[O]rganize Now`, `[R]eturn to Staging`, `[D]iscard`, `[S]kip`, `[Q]uit`.
     - Executes chosen action and updates manifest.

### `media-cron review list`
```bash
media-cron review list [--status pending|resolved|reingested|discarded|all] [--review-dir <path>] [--format text|json]
```
- **Text output**: Table of items (ID, Name, Size, Category Hint, Status, Created Date).
- **JSON output**: Array of `ReviewManifest` JSON objects.

### `media-cron review show <item_id>`
```bash
media-cron review show <item_id> [--review-dir <path>] [--format text|json]
```
- Outputs the full manifest, failure reasons, and contained files.

### `media-cron review resolve <item_id>`
```bash
media-cron review resolve <item_id> \
  --category <movie|tv|music|book|audiobook> \
  --title <text> \
  [--creator <text>] \
  [--year <int>] \
  [--season <int>] \
  [--episode <int>] \
  [--action organize|reingest] \
  [--review-dir <path>] \
  [--dry-run] \
  [--format text|json]
```
- Applies user context directly without interactive prompts.
- Default `--action`: `organize`.

### `media-cron review discard <item_id>`
```bash
media-cron review discard <item_id> [--force] [--review-dir <path>] [--dry-run] [--format text|json]
```
- Requires `--force` in non-interactive mode to prevent accidental deletion.

### `media-cron review purge`
```bash
media-cron review purge --older-than <days> [--force] [--review-dir <path>] [--dry-run] [--format text|json]
```
- Purges items staged longer than `--older-than` days. Requires `--force` if non-interactive.

---

## 3. Global CLI Flags Added to Main Pipeline

Added to `media-cron process` / `media-cron run`:
- `--review-dir PATH`: Directory where unrecognized media files will be staged.
- `--review-max-age-days INT`: Maximum age in days before review items are eligible for purge.

---

## 4. Exit Codes

- `0`: Success (all actions executed without error).
- `1`: General error (validation failure, missing file, non-interactive tty failure).
- `2`: Configuration error (invalid directory path or options).
