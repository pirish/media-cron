# Music Organization and Drop-Folder Ingestion Subsystem

The `media_cron.metadata` music subsystem provides automated music library organization, drop-folder ingestion for external music managers (e.g., `beets`), embedded metadata extraction with filename heuristics, multi-disc and compilation handling, atomic staging for inotify watcher safety, and optional external catalog resolution via MusicBrainz and Discogs.

---

## Subsystem Architecture

```
media_cron/
├── metadata/
│   ├── base.py                   # MusicSpoolEngineProtocol, MusicMetadataProviderProtocol
│   ├── models.py                 # MusicReleaseBundle, MusicTrack, MusicCatalogMatch, etc.
│   ├── cache.py                  # MusicMetadataCache (persistent cache with TTL & atomic save)
│   ├── music_bundler.py          # MusicReleaseBundleAggregator (tracks, discs, companions)
│   ├── music_spooler.py          # MusicSpoolEngine (atomic staging & post-command hook)
│   ├── music_reader.py           # MusicMetadataReader (tinytag extraction & regex fallback)
│   ├── music_identifier.py       # MusicIdentifier (MusicBrainz -> Discogs cascade)
│   └── providers/
│       ├── musicbrainz.py        # MusicBrainzProvider (keyless primary with rate limiter)
│       └── discogs.py            # DiscogsProvider (token-authenticated fallback)
└── plugins/
    └── lookup/
        └── music.py              # MusicLookupPlugin (orchestrates spool, direct, hybrid)
```

---

## Operational Workflow Modes

Configure the active workflow mode via `--music-mode [spool|direct|hybrid]` or in configuration under `music.workflow_mode`:

### 1. Spool Mode (`spool`)
- **Purpose**: Handoff music releases to downstream automated music library managers like `beets`, `Lidarr`, or custom post-processors.
- **Auto-Detection**: If `--music-spool-dir` is provided and `--music-mode` is omitted, the system automatically defaults to `spool` mode.
- **Preserved Hierarchy**: Entire release folders (including nested `CD1/`, `CD2/` subfolders) and companion assets (`cover.jpg`, `album.cue`, `rip.log`, playlists) are clustered into an atomic `MusicReleaseBundle` and transferred to the drop directory.
- **Post-Ingest Command Hook**: Executes optional command templates (e.g., `beet import -q "{release_path}"`) upon successful drop.

### 2. Direct Mode (`direct`)
- **Purpose**: Autonomous standalone library organization without external music managers.
- **Destination Structure**:
  ```
  Music/<Album Artist>/<Album Title> (<Year>)/<Track#> - <Track Title>.<ext>
  ```
- **Multi-Disc Support**: Releases containing multiple discs or disc subfolders are grouped into disc-specific folders (`CD1/`, `CD2/`) or labeled appropriately.
- **Compilation Handling**: Compilations and "Various Artists" releases group tracks under a unified artist directory (`Various Artists` by default) rather than fragmenting tracks into multiple artist folders.

### 3. Hybrid Mode (`hybrid`)
- **Purpose**: Pre-enrich releases with external catalog metadata (canonical year, release ID, match confidence) before depositing them into the external manager's drop directory.

---

## Inotify Watcher Safety & Atomic Staging

To eliminate race conditions with external file watchers (e.g. `inotifywait`, `beets` daemon, `entr`):

1. **Hidden Directory Isolation**:
   Releases are deposited first into a hidden directory on the target filesystem:
   ```
   <spool_dir>/.incoming_<release_name>_<uuid>/
   ```
2. **Transfer Efficiency**:
   Files are hardlinked whenever source and destination reside on the same filesystem (ideal for active seeding torrents). If crossing filesystems, files are copied with automatic cleanup on failure.
3. **Atomic Promotion**:
   Once all tracks and companion files are completely transferred and verified, the hidden folder is atomically renamed to `<spool_dir>/<release_name>` using `os.replace`.
4. **Post-Hook Execution**:
   Optional post-ingest commands are executed only *after* atomic promotion has succeeded.

---

## External Catalog Resolution Cascade

When `--music-lookup` (`music.enable_external_lookup: true`) is enabled:

1. **Local Persistent Cache**: Checks `MusicMetadataCache` (`.media-cron-cache/music_cache.json`).
2. **MusicBrainz Provider** (Primary):
   - Keyless open catalog queries via HTTP API (`https://musicbrainz.org/ws/2/release/`).
   - Built-in rate limiting enforcing maximum 1 request per second.
3. **Discogs Provider** (Fallback):
   - Secondary query executed if primary yields no high-confidence match and `discogs_token` is configured.
4. **Confidence Scoring**:
   - Compares query artist, album, track count, and year using token sort and ratio heuristics.
   - Requires $\ge 85\%$ confidence before canonical catalog metadata may override local tags.
   - Below 85% or when offline, local embedded tags are strictly preserved.

---

## Diagnostic CLI Commands

### `test-music-identify`
Inspect extracted tags and optional catalog matches without modifying any files:
```bash
# Local tag extraction
media-cron test-music-identify /path/to/track.flac

# Test external catalog lookup with JSON output
media-cron test-music-identify /path/to/album_dir --lookup --format json
```

### `test-music-spool`
Test drop-folder deposition and post-ingest command hooks:
```bash
# Dry-run simulation (default)
media-cron test-music-spool /path/to/release --spool-dir /drop/beets_inbox --dry-run

# Live execution with post-hook
media-cron test-music-spool /path/to/release --spool-dir /drop/beets_inbox --no-dry-run --post-command "beet import -q \"{release_path}\""
```

---

## Configuration Reference

```yaml
music:
  enabled: true
  workflow_mode: "spool"                 # "spool" | "direct" | "hybrid"
  spool_dir: "/data/drop/beets"          # Target drop folder
  post_ingest_command: "beet import -q \"{release_path}\""
  preserve_companions: true              # Bundle cover art, cue, log, playlists
  library_dir: "Music"                   # Subfolder in destination library for direct mode
  compilation_artist: "Various Artists"  # Grouping folder for compilations
  enable_external_lookup: false          # Online MusicBrainz/Discogs queries
  confidence_threshold: 0.85             # Override threshold [0.0 - 1.0]
  discogs_token: null                    # Optional Discogs API token
  cache:
    cache_file: ".media-cron-cache/music_cache.json"
    default_ttl: 2592000                 # 30 days in seconds
```
