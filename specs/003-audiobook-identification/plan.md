# Implementation Plan: Audiobook Identification and Author Disambiguation

**Branch**: `003-audiobook-identification` | **Date**: 2026-09-08 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/003-audiobook-identification/spec.md` with explicit architectural directives:
- Automated author and work title identification for audiobooks using local tags and external metadata services.
- Out-of-the-box built-in support for Open Library (default keyless provider) and Audnexus (specialized audiobook provider).
- Multi-file audiobook bundling using album tag consensus and disc subfolder handling (`CD1/`, `Part 2/`) with directory name fallback.
- Explicit conflict precedence: external matches require $\ge 85\%$ match confidence to override local author/title tags.
- Persistent file-based response caching with configurable TTL (default 30 days) to prevent rate limits and ensure <50ms repeat lookups.
- Resilient offline fallback: network timeouts, HTTP 429/5xx, and disabled lookups gracefully fall back to local tags without failing the pipeline.
- Audio classification heuristic: `.m4b` and "audiobook" path hints are treated as audiobooks; general `.mp3`/`.m4a` files in non-audiobook paths require path hints or spoken-word tags before querying book catalogs.

## Summary

Build an audiobook identification and author disambiguation subsystem within `media_cron` that integrates seamlessly into the existing lookup plugin architecture. The design establishes a `MetadataProviderProtocol` and registry, implementing pure Python standard-library adapters for Open Library and Audnexus (`urllib.request`). Multi-file audio tracks are aggregated into cohesive `AudiobookBundle` units prior to query dispatch. A pure Python `ConfidenceScorer` enforces an $85\%$ confidence threshold before external metadata overrides local tags, and a persistent `MetadataCache` minimizes network overhead across recurring cron executions.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**:
- Standard Library: `urllib.request`, `urllib.parse`, `json`, `difflib`, `hashlib`, `pathlib`, `dataclasses`, `enum`, `os`, `time`
- Existing Dependencies: `tinytag` (audio tags), `typer` (CLI), `pyyaml` (configuration)

**Storage**: Local file-based JSON response cache (`.media-cron-cache/audiobook_cache.json`) with atomic write updates.

**Testing**: `pytest`, `pytest-mock`, mock HTTP handlers for external services.

**Target Platform**: Linux servers, containers (Docker / Podman), Kubernetes CronJobs, systemd timers.

**Project Type**: Library-first CLI application (`media_cron` package + `media-cron` CLI binary).

**Performance Goals**:
- Live external metadata queries resolve in < 3.0 seconds under normal network conditions.
- Cached lookups resolve in < 50 milliseconds without initiating outbound network calls.
- Multi-file bundling clusters chapter files in < 100 milliseconds.

**Constraints**:
- Zero additional third-party network runtime dependencies (pure stdlib `urllib.request`).
- Strict confidence threshold ($\ge 85\%$) required to override local author and work title tags.
- 100% predictive `--dry-run` simulation mode with zero filesystem mutations and zero cache pollution.
- Safe offline fallback when external services are disabled, unreachable, or rate-limited.
- Safe handling of special characters, apostrophes, and unicode in book titles and author names.

**Scale/Scope**: Libraries with thousands of audiobook tracks, single-file and multi-disc audiobooks.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Constitutional Principle | Requirement | Compliance Strategy | Status |
|---|---|---|---|
| **I. Library-First & CLI-Driven** | Domain logic decoupled from schedulers; clean text/JSON CLI I/O | Engine in `media_cron.metadata`; provider adapters implementing `MetadataProviderProtocol`; extended CLI flags and diagnostic `test-book-lookup` command | **PASS** |
| **II. Test-First (NON-NEGOTIABLE)** | TDD strictly enforced; unit, contract, and integration tests | Contract tests for `MetadataProviderProtocol`, unit tests for scoring and caching, integration tests for bundling and fallbacks | **PASS** |
| **III. Idempotency & Safety** | Atomic operations, dry-run safety, safe re-runs | Deterministic confidence evaluation; persistent cache; dry-run mode skips file moves and cache writes; offline fallback prevents batch stalls | **PASS** |
| **IV. Observability** | Structured logging, deterministic exit codes, clear telemetry | Telemetry summary includes `audiobook_summary` (provider breakdown, cache hits, confidence); clear warning logs on provider errors | **PASS** |
| **V. Container-Native** | Declarative configuration, separate state/volume mount points | YAML config under `audiobook:`, env var overrides (`MEDIA_CRON_AUDIOBOOK_*`), dedicated cache volume path | **PASS** |

## Project Structure

### Documentation (this feature)

```text
specs/003-audiobook-identification/
├── spec.md              # Feature specification
├── plan.md              # Implementation plan (this file)
├── research.md          # Phase 0: Protocol research, scoring heuristic, cache design
├── data-model.md        # Phase 1: Entity models, schemas, and state transitions
├── quickstart.md        # Phase 1: Runnable verification guide & test scenarios
├── contracts/           # Phase 1: Interface contracts
│   ├── metadata-provider-interface.md  # MetadataProviderProtocol & Registry
│   ├── config-schema.md                # YAML schema & env var specifications
│   └── cli-interface.md                # CLI command options & telemetry schemas
└── checklists/
    └── requirements.md  # Spec quality checklist
```

### Source Code (repository root)

```text
media_cron/
├── cli.py                          # Extended CLI with --audiobook-lookup, --audiobook-provider, test-book-lookup
├── config.py                       # Extended configuration model for audiobook external services & caching
├── models.py                       # Extended MediaAsset (narrator, series, confidence) & BatchSummary
├── metadata/                       # NEW: Audiobook metadata & lookup subsystem
│   ├── __init__.py
│   ├── base.py                     # MetadataProviderProtocol, exceptions, and registry
│   ├── cache.py                    # MetadataCache with atomic persistence & TTL management
│   ├── scorer.py                   # ConfidenceScorer (pure Python difflib + token sets)
│   ├── aggregator.py               # AudiobookBundleAggregator (multi-file clustering)
│   └── providers/
│       ├── __init__.py
│       ├── openlibrary.py          # OpenLibraryProvider implementation
│       └── audnexus.py             # AudnexusProvider implementation
└── plugins/
    └── lookup/
        └── audio.py                # Enhanced AudioTagLookup utilizing metadata subsystem for audiobooks

tests/
├── contract/
│   └── test_metadata_provider_contract.py  # Verifies MetadataProviderProtocol compliance
├── integration/
│   ├── test_audiobook_pipeline.py          # Verifies end-to-end single-file and multi-file pipeline flows
│   ├── test_metadata_caching.py            # Verifies cache hit, expiration, and offline operation
│   └── test_audiobook_quickstart.py        # Verifies quickstart scenarios 1-4
└── unit/
    ├── test_metadata_cache.py              # Verifies cache key generation, TTL, and atomic saves
    ├── test_confidence_scorer.py           # Verifies token scoring, thresholding, and mismatch penalties
    ├── test_audiobook_bundle.py            # Verifies album consensus and disc subfolder clustering
    ├── test_openlibrary_provider.py        # Verifies Open Library URL building and response parsing
    └── test_audnexus_provider.py           # Verifies Audnexus URL building and response parsing
```

**Structure Decision**: Place metadata resolution and external providers under `media_cron/metadata/` as a reusable library module, decoupled from pipeline orchestration. Enhance `AudioTagLookup` in `media_cron/plugins/lookup/audio.py` to delegate audiobook enrichment to this subsystem.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| None | All constitutional principles satisfied | N/A |
