# Media-Cron

**Media-Cron** is a modular, library-first Python CLI tool designed to automate post-download cleanup, media sanitization, container integrity verification, and library organization across video, audio, and literature.

---

## Key Features

- **Pluggable Architecture with Sane Defaults**: Decoupled `InputPlugin`, `LookupPlugin`, and `OutputPlugin` protocols with built-in offline implementations.
- **Staging Directory Isolation**: Moves incoming raw downloads into an isolated `staging_dir` to keep download roots clean and prevent race conditions.
- **Seeding Directory Relocation**: Relocates original files to an optional `seed_dir` with original filenames preserved for continuous torrent seeding while hardlinking organized files into your media server libraries.
- **Filename Sanitization**: Cleans release group tags, tracker URLs, encoding artifacts, and parses movie years, show seasons/episodes, and audio tags.
- **Subtitle Preservation**: Preserves, renames, and moves companion subtitle files (`.srt`, `.ass`, `.sub`, `.vtt`) alongside their parent video files.
- **Clutter Purging**: Prunes junk files (`.nfo`, `.txt`, `.url`, `.sfv`, etc.) and sample clips under 50 MB, followed by empty parent directory cleanup.
- **Container Integrity Verification**: Inspects Matroska EBML, MP4 atoms, audio magic bytes, and e-book archives, preventing corrupt or truncated downloads from contaminating libraries.
- **Concurrency Protection**: Non-blocking staging lockfile (`.media-cron.lock`) protects automated cron jobs from running concurrently.
- **Dry-Run Simulation**: 100% predictive `--dry-run` simulation mode with zero filesystem writes.
- **Dual Output Streams**: Clean human-readable text logs or structured JSON for automated script integration.

---

## Installation

```bash
# Clone and install in editable mode
git clone <repo-url> media-cron
cd media-cron
pip install -e ".[dev]"
```

---

## Quickstart & Usage

### 1. Dry-Run Simulation

Preview all planned renames, deletions, and moves without modifying any files:

```bash
media-cron organize \
  --source /downloads/completed \
  --staging /data/staging \
  --destination /media/library \
  --dry-run \
  --format text
```

Or get machine-readable JSON:

```bash
media-cron organize \
  --source /downloads/completed \
  --destination /media/library \
  --dry-run \
  --format json
```

### 2. Live Execution with Hardlinks & Seeding

```bash
media-cron organize \
  --source /downloads/completed \
  --staging /data/staging \
  --destination /media/library \
  --seed-dir /downloads/seeding \
  --mode hardlink
```

---

## Configuration (`~/.config/media-cron/config.yaml`)

```yaml
paths:
  source_dir: "/downloads/completed"
  staging_dir: "/data/staging"
  destination_dir: "/media/library"
  seed_dir: "/downloads/seeding"

general:
  mode: "hardlink" # Options: hardlink, move, copy
  dry_run: false
  sample_size_threshold_mb: 50
  junk_extensions:
    - ".nfo"
    - ".txt"
    - ".url"
    - ".sfv"
    - ".exe"
    - ".m3u"

templates:
  movie: "Movies/{title} ({year})/{title} ({year}).{ext}"
  series: "TV Shows/{show}/Season {season:02d}/{show} - S{season:02d}E{episode:02d}.{ext}"
  music: "Music/{artist}/{album}/{track:02d} - {title}.{ext}"
  audiobook: "Audiobooks/{author}/{title}/{track:02d} - {title}.{ext}"
  book: "Books/{author}/{title}.{ext}"

plugins:
  input: "directory_scanner"
  lookups:
    - "scene_video"
    - "audio_tag"
    - "book_meta"
  outputs:
    - "library_organizer"
    - "seed_relocator"
    - "junk_cleaner"
```

### Environment Variable Overrides

- `MEDIA_CRON_SOURCE_DIR`
- `MEDIA_CRON_STAGING_DIR`
- `MEDIA_CRON_DESTINATION_DIR`
- `MEDIA_CRON_SEED_DIR`
- `MEDIA_CRON_MODE`
- `MEDIA_CRON_DRY_RUN`
- `MEDIA_CRON_CONFIG`

---

## Cron & Automation Setup

Example `/etc/cron.d/media-cron` job running every 15 minutes:

```cron
*/15 * * * * user media-cron organize --config /etc/media-cron/config.yaml --format json >> /var/log/media-cron.log 2>&1
```

If a prior job is still running, the non-blocking lockfile will cause subsequent executions to exit immediately with exit code `1` and a logged notice, preventing race conditions.

---

## Development & Quality Gates

### Pre-Commit Hooks

Media-Cron uses [pre-commit](https://pre-commit.com/) to automatically enforce file hygiene, Ruff linting/formatting, and the complete test suite before any commit is finalized:

```bash
# Install git pre-commit hooks
pre-commit install

# Run all hooks manually across the entire repository
pre-commit run --all-files
```

### Running Tests & Linters Manually

```bash
# Run full automated test suite
pytest -v

# Run lint checks
ruff check .

# Run code formatter check
ruff format --check .
```

---

## Container & Kubernetes Deployment

### Docker / Podman

Media-Cron publishes non-root multi-architecture container images (`linux/amd64` and `linux/arm64`) to GitHub Container Registry:

```bash
docker run --rm \
  -v /downloads/completed:/data/completed \
  -v /data/staging:/data/staging \
  -v /media/library:/data/library \
  -v ~/.config/media-cron/config.yaml:/config/config.yaml:ro \
  ghcr.io/pirish/media-cron:latest organize
```

### Kubernetes Helm Chart

Deploy Media-Cron to Kubernetes clusters using the official OCI Helm chart:

```bash
# Deploy as a scheduled batch CronJob (default)
helm install media-cron oci://ghcr.io/pirish/charts/media-cron \
  --set persistence.data.existingClaim=media-storage-pvc \
  --set cronjob.schedule="0 2 * * *"

# Or deploy as a continuous background daemon
helm install media-cron oci://ghcr.io/pirish/charts/media-cron \
  --set workloadType=Deployment
```
