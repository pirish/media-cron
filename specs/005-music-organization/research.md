# Technical Research: Music Library Organization and Drop-Folder Ingestion

**Feature**: `005-music-organization`
**Date**: 2026-09-09
**Status**: Completed

---

## 1. External Library Manager Drop-Folder Ingestion & In-Flight Race Prevention

### Problem Statement
Users who manage large music collections frequently utilize dedicated music curation systems (such as `beets`, `Lidarr`, or `MusicBrainz Picard`). These external tools often employ filesystem watchers (`inotify`, `beet-watch`, or daemon cron loops) that automatically trigger an import as soon as a new directory or file is detected in the drop/spool folder. Transferring multi-gigabyte lossless albums (FLAC/ALAC) or multi-track releases file-by-file causes race conditions where downstream watchers begin importing partial albums before all tracks, `.cue` sheets, or artwork have finished copying.

### Decision
Implement an atomic staging protocol within `media_cron.metadata.music_spooler`:
1. **Hidden Staging Directory**: When depositing a release bundle into `spool_dir`, create a hidden sibling folder: `.incoming_<sanitized_release_name>_<uuid4_prefix>`.
2. **Transfer Execution**: Transfer audio files and companion assets into the hidden staging directory using the configured mode (`hardlink` with automatic `copy` fallback when across filesystems).
3. **Integrity Verification**: Verify that all queued track files and companion assets are fully written, non-zero in byte size, and accessible.
4. **Atomic Promotion**: Atomically rename `.incoming_<release_name>_<uuid4_prefix>` to the final target release directory (`<sanitized_release_name>`). On POSIX systems, `os.replace` on directories within the same filesystem is an atomic operation.
5. **Post-Ingest Command Hook**: If `--music-post-command` / `post_ingest_command` is configured (e.g. `beet import -q "{release_path}"`), invoke the command via `subprocess.run` with a configurable timeout (default 60s), capturing stdout/stderr into structured logs without crashing the cron batch on external tool errors.

### Alternatives Considered
- *Direct File Copy*: Copying directly into the root or destination folder. Rejected because inotify watchers trigger prematurely on incomplete multi-track releases.
- *Lockfile Sentinel*: Creating `.media-cron.lock` inside the folder. Rejected because external tools like `beets` do not natively check custom lockfiles by default.

---

## 2. Audio Tag Extraction & Format Support

### Problem Statement
Music collections encompass a diverse matrix of container formats (`.mp3`, `.flac`, `.m4a`, `.ogg`, `.opus`, `.wav`, `.alac`, `.aiff`). The system must extract track titles, artist, album artist, album, track number, disc number, release year, and genre with high performance and zero new external runtime dependencies.

### Decision
Utilize the existing `tinytag` dependency (already declared in `pyproject.toml` and proven across the codebase in `media_cron.plugins.lookup.audio`):
1. **Format Handling**: `tinytag.TinyTag` parses ID3v1/v2, Vorbis Comments, FLAC metadata blocks, and MP4 atoms with pure Python standard library bindings in under 10ms per track.
2. **Filename Fallback**: When tags are missing or stripped, implement a deterministic regex parser extracting track number, artist, and title from standard file naming conventions (e.g., `01 - Title.flac`, `Artist - Title.mp3`, `01. Artist - Title.m4a`).
3. **Release Bundling**: Group files sharing a parent directory or sharing `album` and `albumartist` tags into a coherent `MusicReleaseBundle`. Multi-disc releases (`Disc 1`, `CD 02`) under a shared parent folder are clustered into a single parent release bundle.

### Alternatives Considered
- *Adding `mutagen`*: While feature-rich, adding mutagen introduces a new dependency. `tinytag` is already present in `pyproject.toml`, pure-Python, and lightweight.
- *Pure Standard Library Binary Parsers*: Writing custom binary parsers for ID3, FLAC, and MP4. Deemed unnecessary complexity given `tinytag` is already vetted in the project.

---

## 3. External Catalog Provider Cascade: MusicBrainz & Discogs

### Problem Statement
When automatic external identification is enabled, the system must query canonical catalog databases to identify releases, verify tracklists, and resolve album artists without requiring mandatory API keys.

### Decision
Implement a multi-provider cascade adhering to `MetadataProviderProtocol`:
1. **Primary Provider (`MusicBrainzProvider`)**:
   - Keyless open-access REST API (`https://musicbrainz.org/ws/2/release/`).
   - Queries using release title, album artist, and track count filters.
   - Enforces a client rate limiter (maximum 1 request per second) and sends a compliant descriptive `User-Agent` header (`media-cron/1.0.0 ( mailto:admin@example.com )`).
   - Retrieves canonical MusicBrainz Release ID, Artist Credit, Release Date, and Tracklist.
2. **Secondary Fallback Provider (`DiscogsProvider`)**:
   - Authenticated REST API (`https://api.discogs.com/database/search`).
   - Active only when optional credentials (`discogs_token`) are supplied.
   - Used when MusicBrainz returns no candidates or is unreachable.
3. **Confidence Scoring & Precedence**:
   - Employs `ConfidenceScorer` (token sort + fuzzy ratio).
   - $\ge 85\%$ confidence: External release and artist information can standardize local metadata.
   - $< 85\%$ confidence or offline: Strict preservation of embedded tags and local heuristics.

### Alternatives Considered
- *Spotify Web API*: Requires OAuth2 client credentials and has strict developer terms; unsuitable for keyless zero-configuration operation.
- *Last.fm API*: Lacks robust release-level tracklist and multi-disc validation compared to MusicBrainz.

---

## 4. Companion Asset Bundling

### Problem Statement
Music releases contain vital non-audio assets that must accompany the audio files for external managers:
- Cover artwork: `cover.jpg`, `folder.jpg`, `front.png`, `artwork.jpeg`
- Cuesheets and logs: `.cue`, `.log`, `.accurip`
- Playlists and checksums: `.m3u`, `.m3u8`, `.sfv`, `.md5`

### Decision
Define a canonical companion file extension and filename filter:
1. When assembling a `MusicReleaseBundle`, scan the release folder for companion files matching `COMPANION_EXTENSIONS = {".jpg", ".jpeg", ".png", ".cue", ".log", ".accurip", ".m3u", ".m3u8", ".sfv", ".md5"}`.
2. Filter out generic unwanted files (e.g. `.nfo`, `.url`, `.txt` unless matching artwork/cue/log).
3. In `spool` mode, transfer all bundled companion assets into the hidden staging directory alongside audio tracks before atomic promotion.
4. In `direct` mode, copy/link `cover.jpg` and `.cue` files into the organized album destination directory.

---

## 5. Summary of Architecture Decisions

| Area | Decision | Key Benefits |
|---|---|---|
| **Drop Handoff** | Atomic hidden directory staging (`.incoming_<name>`) | Eliminates race conditions with external `inotify` watchers |
| **Post Hook** | Optional shell command hook (`--music-post-command`) | Direct integration with `beet import` or custom scripts |
| **Tag Extraction** | `tinytag` + regex filename heuristics | High speed, broad codec support, zero new dependencies |
| **Online Provider** | MusicBrainz primary + Discogs optional fallback | Keyless default, open data, high fidelity metadata |
| **Bundling** | Directory + tag-based `MusicReleaseBundleAggregator` | Unified multi-disc and album handling with companion assets |
