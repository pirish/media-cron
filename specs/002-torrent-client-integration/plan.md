# Implementation Plan: Torrent Client Integration for Ingestion and Seeding Management

**Branch**: `002-torrent-client-integration` | **Date**: 2026-09-07 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-torrent-client-integration/spec.md` with explicit architectural directives:
- Direct interaction with torrent clients for ingestion and seeding relocation.
- First-class built-in support for qBittorrent, with pluggable client architecture for Transmission and Deluge.
- Configurable staging isolation (always copy to staging to keep original payload intact for seeding).
- Preserving non-media clutter in the torrent client seeding storage to ensure 100% tracker verification.
- Dual state tracking (completion tag `media-cron-processed` AND category `media-cron-done`) for idempotency.
- Hybrid ingestion mode supporting simultaneous drop folder and torrent client monitoring.

## Summary

Integrate torrent client capabilities directly into `media-cron` to automate ingestion of completed downloads, bridge Docker container path differences via declarative prefix mapping, manage seeding relocation through client APIs (`setLocation`), and enforce idempotency through dual tagging and category updates. The architecture establishes a `TorrentClientProtocol` with a built-in `QBittorrentClient` using Python standard library `urllib.request` (zero external dependencies). New `TorrentInputPlugin` and `TorrentClientSeedOutput` plugins seamlessly integrate with `media-cron`'s existing pipeline and staging lock engine.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**:
- Standard Library: `urllib.request`, `http.cookiejar`, `json`, `pathlib`, `shutil`, `fcntl`, `dataclasses`, `enum`
- CLI & Configuration: `typer` (CLI entry point & argument parsing), `pyyaml` (configuration)
- Metadata: `tinytag` (audio metadata extraction)

**Storage**: Local and remote POSIX filesystems, container volume mounts, declarative `PathMappingRule` translations.

**Testing**: `pytest`, `pytest-mock`, `urllib` mock response handlers.

**Target Platform**: Linux servers, containers (Docker / Podman), Kubernetes CronJobs, systemd timers.

**Project Type**: Library-first CLI application (`media_cron` package + `media-cron` CLI binary).

**Performance Goals**:
- Query and filter 200 torrents in < 3 seconds.
- Execute path translation and staging copy operations in < 5 seconds (excluding physical cross-device I/O).

**Constraints**:
- Zero additional external runtime dependencies (pure stdlib HTTP/Cookie client).
- 100% predictive `--dry-run` simulation mode with zero filesystem mutations and zero client state changes.
- Non-blocking single-instance concurrency via existing `.media-cron.lock` in `staging_dir`.
- Retention of all clutter in the client seeding path to ensure 100% tracker hash integrity.
- Credential masking for all usernames, passwords, and tokens in logs and CLI outputs.

**Scale/Scope**: Clients with hundreds of active torrents; multi-gigabyte media payloads.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Constitutional Principle | Requirement | Compliance Strategy | Status |
|---|---|---|---|
| **I. Library-First & CLI-Driven** | Domain logic decoupled from schedulers; clean text/JSON CLI I/O | Client adapter in `media_cron.torrent`; plugins in `media_cron.plugins`; CLI commands with `--format json` | **PASS** |
| **II. Test-First (NON-NEGOTIABLE)** | TDD strictly enforced; unit, contract, and integration tests | Mocked API contract tests and unit tests written before client and plugin implementations | **PASS** |
| **III. Idempotency & Safety** | Atomic operations, dry-run safety, lockfile concurrency, safe re-runs | Dual tag+category tracking, staging lockfile, predictive dry-run mode, clutter preservation | **PASS** |
| **IV. Observability** | Structured logging, deterministic exit codes (0, 1, 2, 3), credential masking | Exit codes standardized (`EXIT_SUCCESS`, `EXIT_CONFIG_ERROR`, etc.), passwords masked in logs | **PASS** |
| **V. Container-Native** | Declarative configuration, separate state/volume mount points | `PathMappingRule` for container mounts, `MEDIA_CRON_*` env vars, declarative YAML schema | **PASS** |

## Project Structure

### Documentation (this feature)

```text
specs/002-torrent-client-integration/
├── spec.md              # Feature specification
├── plan.md              # Implementation plan (this file)
├── research.md          # Phase 0: Technical evaluations & protocol research
├── data-model.md        # Phase 1: Entities, state transitions, and schemas
├── quickstart.md        # Phase 1: Runnable verification guide & test scenarios
├── contracts/           # Phase 1: Interface contracts
│   ├── torrent-client-interface.md  # TorrentClientProtocol & Registry
│   ├── cli-interface.md             # CLI command syntax, options, and JSON telemetry
│   └── config-schema.md             # YAML configuration & env var specifications
└── checklists/
    └── requirements.md  # Spec quality checklist
```

### Source Code (repository root)

```text
media_cron/
├── cli.py                       # Extended CLI with --torrent-client, --torrent-hash, test-client
├── config.py                    # Extended configuration loader for torrent clients & path mappings
├── models.py                    # Extended domain models (OperationType, BatchSummary telemetry)
├── pipeline.py                  # Core pipeline orchestrating hybrid & torrent plugins
├── plugins/
│   ├── input/
│   │   ├── directory.py         # DirectoryScannerInput (existing)
│   │   └── torrent.py           # NEW: TorrentInputPlugin (discovers & copies to staging)
│   └── output/
│       ├── organizer.py         # LibraryOrganizerOutput (existing)
│       ├── seed.py              # SeedRelocatorOutput (existing direct filesystem)
│       └── torrent_seed.py      # NEW: TorrentClientSeedOutput (setLocation & tagging)
└── torrent/
    ├── __init__.py
    ├── base.py                  # NEW: TorrentClientProtocol & TorrentClientRegistry
    ├── models.py                # NEW: TorrentItem, TorrentFile, PathMappingRule, TorrentState
    └── clients/
        ├── __init__.py
        └── qbittorrent.py       # NEW: QBittorrentClient (Web API v2 implementation)

tests/
├── contract/
│   └── test_torrent_client_contract.py  # Verifies TorrentClientProtocol compliance
├── integration/
│   ├── test_qbittorrent_integration.py  # Verifies end-to-end mock qBittorrent flows
│   └── test_hybrid_pipeline.py          # Verifies simultaneous folder + client ingestion
└── unit/
    ├── test_path_mapping.py             # Verifies prefix replacement and resolution
    ├── test_qbittorrent_client.py       # Verifies Web API v2 endpoints and error handling
    └── test_torrent_plugins.py          # Verifies TorrentInputPlugin and TorrentClientSeedOutput
```

**Structure Decision**: Builds directly upon the established modular architecture of `media_cron` from Feature 001. Adds a dedicated `media_cron.torrent` subpackage to encapsulate external client protocols and client models, while implementing new `InputPlugin` and `OutputPlugin` classes that plug directly into the existing `Pipeline` without breaking backwards compatibility.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| None | Fully compliant with all 5 principles of the Media-Cron Constitution | N/A |
