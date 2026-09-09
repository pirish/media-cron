# Implementation Plan: Music Library Organization and Drop-Folder Ingestion

**Branch**: `005-music-organization` | **Date**: 2026-09-09 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/005-music-organization/spec.md` with explicit architectural directives:
- Support two distinct workflows: depositing media into an external manager's drop folder (such as `beets`, `Lidarr`, `Picard`) and direct internal organization into the media library.
- Automatic identification supported as an optional, non-blocking feature with local-first offline fallback.
- In drop-folder (`spool`) mode, preserve release folder hierarchies and bundle companion assets (`.jpg`, `.png`, `.cue`, `.log`, `.m3u`).
- Atomic directory staging (`.incoming_<release_name>`) on the drop filesystem to prevent external `inotify` watchers from triggering on partial transfers.
- Optional post-ingest command execution hook (`--music-post-command` / `post_ingest_command`) with subprocess timeouts and error containment.
- Multi-provider cascade for optional online catalog lookups: MusicBrainz as keyless primary, Discogs as optional authenticated secondary.
- Hardlink mode support to preserve active torrent seeding.
- 100% predictive `--dry-run` simulation mode with zero filesystem mutations.

---

## Summary

Build a unified music library organization and drop-folder handoff subsystem within `media_cron`:
1. A `MusicReleaseBundleAggregator` that clusters multi-track audio files, subdirectories (`Disc 1`, `CD 2`), and companion files (artwork, cuesheets, logs) into cohesive `MusicReleaseBundle` entities.
2. A `MusicSpoolEngine` in `media_cron.metadata.music_spooler` implementing atomic hidden directory staging (`.incoming_<id>` → `<final>`), hardlink transfer with copy fallback, and optional post-ingest command execution.
3. A format-aware `MusicMetadataReader` wrapping `tinytag` and regex filename parsing for embedded tag extraction across `.mp3`, `.flac`, `.m4a`, `.ogg`, `.opus`, `.wav`, `.alac`, `.aiff`.
4. A `MusicBrainzProvider` adapter querying the keyless MusicBrainz REST API (`/ws/2/release/`) with rate limiting (1 req/s) and caching, with optional `DiscogsProvider` fallback.
5. Integration into `MusicLookupPlugin` (`media_cron.plugins.lookup.music`), CLI options (`--music-mode`, `--music-spool-dir`, `--music-post-command`), and diagnostic commands (`test-music-identify`, `test-music-spool`).

---

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**:
- Standard Library: `pathlib`, `json`, `subprocess`, `shutil`, `urllib.request`, `urllib.parse`, `dataclasses`, `enum`, `re`, `time`
- Existing Dependencies: `tinytag` (audio metadata extraction), `typer` (CLI), `pyyaml` (configuration)

**Storage**: Local file-based JSON response cache (`.media-cron-cache/music_cache.json`) with atomic write updates.

**Testing**: `pytest`, `pytest-mock`, synthetic audio and companion test files.

**Target Platform**: Linux servers, containers (Docker / Podman), Kubernetes CronJobs, systemd timers.

**Project Type**: Library-first CLI application (`media_cron` package + `media-cron` CLI binary).

**Performance Goals**:
- Embedded tag extraction completes in < 20 milliseconds per audio track.
- Atomic directory promotion executes in < 5 milliseconds on same-filesystem drop folders.
- Cached catalog responses resolve in < 50 milliseconds without outbound network calls.
- Post-ingest command execution enforces a configurable subprocess timeout (default 120s).

**Constraints**:
- Zero additional third-party Python runtime dependencies (utilizing standard library + existing `tinytag`).
- Non-destructive execution: failed transfers clean up temporary staging directories without touching source files.
- Inotify safety: external watchers must never see partial or in-flight files in drop folders.
- 100% predictive `--dry-run` simulation mode with zero filesystem mutations.

**Scale/Scope**: Music collections spanning hundreds of gigabytes and thousands of albums.

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Constitutional Principle | Requirement | Compliance Strategy | Status |
|---|---|---|---|
| **I. Library-First & CLI-Driven** | Domain logic decoupled from schedulers; clean text/JSON CLI I/O | Spooler, bundler, and reader built as standalone library modules under `media_cron.metadata`; exposed via CLI flags and diagnostic commands (`test-music-identify`, `test-music-spool`) supporting text and JSON output | **PASS** |
| **II. Test-First (NON-NEGOTIABLE)** | TDD strictly enforced; unit, contract, and integration tests | Contract tests for `MusicSpoolEngineProtocol` and `MusicMetadataProviderProtocol`, unit tests for readers and spoolers, integration tests for full pipeline and dry-run safety | **PASS** |
| **III. Idempotency & Safety** | Atomic operations, dry-run safety, safe re-runs | Atomic hidden directory promotion (`.incoming_<name>` → `<name>`); non-destructive defaults; `--dry-run` guarantees zero disk mutations; safe cleanup of interrupted transfers | **PASS** |
| **IV. Observability** | Structured logging, deterministic exit codes, clear telemetry | Structured logging at INFO/DEBUG/WARNING; deterministic exit codes (0, 1, 2); machine-readable telemetry in `music_summary` | **PASS** |
| **V. Container-Native** | Declarative configuration, separate state/volume mount points | YAML configuration under `music:`, environment variables (`MEDIA_CRON_MUSIC_*`), isolated `.media-cron-cache/` directory | **PASS** |

---

## Project Structure

### Documentation (this feature)

```text
specs/005-music-organization/
├── plan.md              # This file
├── research.md          # Technical research & decisions (Phase 0)
├── data-model.md        # Domain models & entities (Phase 1)
├── quickstart.md        # Quickstart validation guide (Phase 1)
├── contracts/           # Interface contracts (Phase 1)
│   ├── cli-interface.md
│   ├── config-schema.md
│   ├── spool-engine-interface.md
│   └── music-provider-interface.md
└── checklists/
    └── requirements.md  # Quality checklist
```

### Source Code Layout

```text
media_cron/
├── config.py                             # MusicConfig additions
├── models.py                             # BatchSummary.music_summary additions
├── metadata/
│   ├── models.py                         # MusicTrack, MusicReleaseBundle, MusicSpoolResult
│   ├── music_reader.py                   # Format-aware audio tag extractor (tinytag + heuristics)
│   ├── music_bundler.py                  # Release bundle & companion asset aggregator
│   ├── music_spooler.py                  # Atomic drop-folder staging & post-command runner
│   ├── music_identifier.py               # Identification coordinator & confidence resolution
│   └── providers/
│       ├── musicbrainz.py                # MusicBrainz REST adapter (keyless primary)
│       └── discogs.py                    # Discogs REST adapter (authenticated secondary)
├── plugins/
│   └── lookup/
│       └── music.py                      # MusicLookupPlugin
└── cli.py                                # CLI flags & test-music-* commands

tests/
├── contract/
│   ├── test_music_spooler_contract.py    # Verifies MusicSpoolEngineProtocol
│   └── test_music_provider_contract.py   # Verifies MusicMetadataProviderProtocol
├── unit/
│   └── metadata/
│       ├── test_music_reader.py          # Embedded tag extraction & regex fallback
│       ├── test_music_bundler.py         # Multi-track & companion bundling
│       ├── test_music_spooler.py         # Atomic staging & post-command execution
│       └── test_music_identifier.py      # Confidence scoring & cascade
└── integration/
    ├── test_music_cli.py                 # CLI diagnostic & process flags
    ├── test_music_spool.py               # Drop-folder workflow end-to-end
    ├── test_music_direct.py              # Direct library organization
    └── test_music_quickstart.py          # Quickstart scenarios 1-5 verification
```

---

## Complexity Tracking

> *No constitutional violations detected. Clean adherence to Core Principles.*
