# Implementation Plan: Standalone Media File Organizer and Cleaner CLI

**Branch**: `001-media-cleaner-organizer` | **Date**: 2026-09-04 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-media-cleaner-organizer/spec.md` with explicit architectural directives:
- Pluggable interfaces (input, lookup, output) with sane offline defaults.
- Mandatory staging directory workflow so raw incoming files are isolated.
- User-configurable seed directory relocation for ongoing torrent seeding.

## Summary

Build a standalone, library-first Python CLI tool that automates post-download cleanup, media sanitization, container integrity verification, and library organization across video, audio, and literature. The architecture employs a pluggable pipeline pattern with built-in sane defaults:
1. **Input Ingestion**: Discovers media and moves it atomically to a user-configured `staging_dir`.
2. **Lookup & Sanitization**: Parses messy release tags and extracts metadata offline using modular regex, tag, and container inspectors.
3. **Integrity Verification**: Inspects magic bytes and headers (EBML/Matroska, MP4 atoms, ZIP/PDF headers) before any relocation.
4. **Output Disposition**: Organizes assets into customizable library hierarchies via atomic hardlinks or moves, optionally mirrors source material into a dedicated `seed_dir`, and prunes clutter and empty directories.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**:
- Standard Library: `pathlib`, `typing`, `dataclasses`, `fcntl`, `re`, `shutil`, `uuid`, `datetime`
- CLI & Configuration: `typer` / `click` (rich CLI with JSON output), `pyyaml` (configuration)
- Audio/Media Metadata: `tinytag` (lightweight pure-Python tag reader for audio/music)

**Storage**: Local and network POSIX filesystems; atomic operations via `os.link` and `os.replace`

**Testing**: `pytest`, `pytest-mock`, `coverage`

**Target Platform**: Linux servers, containers (Docker / Podman), Kubernetes CronJobs, systemd timers

**Project Type**: Library-first CLI application (`media_cron` package + `media-cron` CLI binary)

**Performance Goals**: Process, verify, and organize 50 media assets in < 5 seconds

**Constraints**:
- Offline-first: zero network dependencies required for standard operation.
- Non-blocking single-instance concurrency via `.media-cron.lock` in `staging_dir`.
- 100% predictive `--dry-run` simulation mode with zero filesystem writes.

**Scale/Scope**: Multi-terabyte media collections; single batch runs up to 500 media files.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Constitutional Principle | Requirement | Compliance Strategy | Status |
|---|---|---|---|
| **I. Library-First & CLI-Driven** | Core logic isolated in reusable Python modules; clean text/JSON CLI I/O | All orchestration in `media_cron.pipeline`; CLI in `media_cron.cli` with `--format json` support | **PASS** |
| **II. Test-First (NON-NEGOTIABLE)** | TDD strictly enforced; unit and contract tests written before implementation | Tests partitioned into `tests/contract`, `tests/integration`, and `tests/unit` | **PASS** |
| **III. Idempotency & Safety** | Atomic moves/links, dry-run mode, concurrency lockfile, safe collision handling | Atomic `os.link`/`os.replace`, non-blocking `fcntl.flock`, quality-based upgrade logic | **PASS** |
| **IV. Observability** | Structured logging, deterministic exit codes (0, 1, 2, 3) | Deterministic exit constants, standardized JSON output schema | **PASS** |
| **V. Container-Native** | Declarative configuration, separate state/volume mount points | `MEDIA_CRON_*` env vars, separate `staging_dir`, `seed_dir`, and `destination_dir` | **PASS** |

## Project Structure

### Documentation (this feature)

```text
specs/001-media-cleaner-organizer/
├── spec.md              # Feature specification
├── plan.md              # Implementation plan (this file)
├── research.md          # Technical evaluations & architecture decisions
├── data-model.md        # Entities, state transitions, and schemas
├── quickstart.md        # Runnable verification guide & test scenarios
├── contracts/           # Interface contracts
│   ├── plugin-interfaces.md  # Input, Lookup, and Output plugin protocols
│   ├── cli-interface.md      # Command syntax, flags, JSON schema, and exit codes
│   └── config-schema.md      # YAML configuration schema and env var mappings
└── checklists/
    └── requirements.md  # Spec quality checklist
```

### Source Code (repository root)

```text
media_cron/
├── __init__.py
├── cli.py               # CLI entry points and argument parsing
├── config.py            # Configuration loader and env var resolution
├── lock.py              # Non-blocking lockfile management (fcntl)
├── models.py            # Domain dataclasses (MediaAsset, OperationPlan, etc.)
├── pipeline.py          # Core pipeline orchestration engine
├── plugins/
│   ├── __init__.py
│   ├── base.py          # Abstract Protocols (InputPlugin, LookupPlugin, OutputPlugin)
│   ├── registry.py      # Plugin discovery and registry
│   ├── input/
│   │   ├── __init__.py
│   │   └── directory.py # Built-in: DirectoryScannerInput (with staging move)
│   ├── lookup/
│   │   ├── __init__.py
│   │   ├── video.py     # Built-in: Scene regex video lookup & sanitization
│   │   ├── audio.py     # Built-in: Audio tag lookup (tinytag)
│   │   └── book.py      # Built-in: E-book metadata lookup (epub/pdf)
│   └── output/
│       ├── __init__.py
│       ├── organizer.py # Built-in: LibraryOrganizerOutput (hardlink/move + template)
│       ├── seed.py      # Built-in: SeedRelocatorOutput (seed dir preservation)
│       └── cleaner.py   # Built-in: JunkCleanerOutput (clutter & empty dir prune)
└── integrity/
    ├── __init__.py
    └── validator.py     # Container header and magic bytes inspection

tests/
├── conftest.py          # Shared fixtures (temp staging, fixtures, mock assets)
├── contract/
│   ├── test_input_contract.py
│   ├── test_lookup_contract.py
│   └── test_output_contract.py
├── integration/
│   ├── test_cli_e2e.py
│   ├── test_pipeline_integration.py
│   └── test_staging_seeding.py
└── unit/
    ├── test_cleaner.py
    ├── test_config.py
    ├── test_integrity.py
    ├── test_lock.py
    ├── test_naming.py
    └── test_path_templates.py
```

**Structure Decision**: Single modular Python project with clean separation between core domain pipeline, pluggable components (`plugins/`), and consumer entry point (`cli.py`).

## Complexity Tracking

*No constitutional violations. All designs comply with Core Principles without exceptions.*
