<!--
Sync Impact Report:
- Version change: 0.0.0 (template) → 1.0.0
- Principles established:
  - Principle I: Library-First & CLI-Driven
  - Principle II: Test-First & Contract Verification (NON-NEGOTIABLE)
  - Principle III: Idempotency & Failure Resilience
  - Principle IV: Structured Observability & Diagnosability
  - Principle V: Container-Native & Environment Isolation
- Added sections:
  - Technical Stack & Integration Standards
  - Development Workflow & Quality Gates
- Removed sections: None (initialized from template)
- Follow-up TODOs: None
-->

# Media-Cron Constitution

## Core Principles

### I. Library-First & CLI-Driven
Domain logic for media organization, post-download cleanup, and torrent/library client
integrations MUST be developed as standalone, reusable Python library modules decoupled from
schedulers and cron execution. Each module MUST expose its core functionality via a dedicated
CLI entry point following standard UNIX text stream conventions (arguments/stdin → stdout,
errors → stderr). CLI commands MUST support both machine-parsable JSON output and human-readable
text formatting.

### II. Test-First & Contract Verification (NON-NEGOTIABLE)
Test-driven development (TDD) is mandatory. Unit tests MUST verify cleanup heuristics, file
parsing, naming rules, and organization logic before implementation code is written. Integration
and contract tests MUST mock and validate interactions with external client APIs (such as
qBittorrent, Transmission, Deluge, Plex, Jellyfin, Sonarr, and Radarr). Red-green-refactor cycles
are strictly enforced; PRs without corresponding automated tests MUST NOT be merged.

### III. Idempotency & Failure Resilience
All cron jobs, cleanup routines, and media processing operations MUST be idempotent and safe to
re-run against the same filesystem state. File operations MUST employ atomic moves/links and
verify destination state before modification. Concurrent executions MUST be prevented via explicit
file locking or single-instance mutex mechanisms. Non-destructive execution MUST be the default;
all operations capable of modifying or deleting files MUST provide a verified dry-run mode.

### IV. Structured Observability & Diagnosability
Every execution MUST emit structured logging with consistent log levels (DEBUG, INFO, WARNING,
ERROR) and predictable machine-readable formats. Process exit codes MUST be deterministic: 0 for
success, and distinct non-zero codes for configuration errors, missing dependencies, external
client connection failures, or filesystem permissions. Unattended cron runs MUST operate cleanly
without noisy unhandled stack traces, while providing verbose flags for local troubleshooting.

### V. Container-Native & Environment Isolation
Media-Cron components MUST be designed for seamless deployment both in bare-metal Linux environments
and containerized systems (Docker, Podman, Kubernetes CronJobs). Configuration MUST be fully
declarative via environment variables and structured configuration files (YAML/JSON). Persistent
state, including logs, processed history caches, and lockfiles, MUST be isolated to dedicated
directories suitable for volume mounts.

## Technical Stack & Integration Standards

- **Language & Runtime**: Python 3.11+ using modern type annotations, structured project
  management (e.g., standard packaging, dependency pinning), and robust linting/testing (ruff,
  pytest).
- **Client Integrations**: Standardized API/RPC client wrappers for torrent clients and media
  servers. All network interactions MUST incorporate timeouts, retry policies, and graceful
  fallbacks when target services are unreachable.
- **Filesystem & Subprocess Handling**: Media path handling MUST use strict path resolution
  (`pathlib`), handle unicode and special characters safely, and preserve permissions. External
  tool invocations (e.g., mediainfo, ffmpeg, mkvmerge) MUST specify timeouts and capture structured
  error outputs.

## Development Workflow & Quality Gates

- **Specification First**: Features, cleanup rules, and integrations MUST begin with an approved
  specification using Spec Kit workflows prior to code implementation.
- **Automated Verification**: Every change MUST pass automated linting, formatting, type checking,
  and unit/integration test suites.
- **Dry-Run & Safety Validation**: Any routine that moves, deletes, or modifies media files MUST
  include automated tests specifically validating dry-run accuracy and boundary conditions (e.g.,
  symlink loops, missing destinations, read-only permissions, or partial downloads).

## Governance

This constitution supersedes all informal or ad-hoc practices across the Media-Cron project.
All proposed changes, feature specifications, and pull requests MUST verify compliance with the
Core Principles. Amendments to this document require explicit documentation, an impact assessment
on existing cron tasks and integrations, and a semantic version bump:
- **MAJOR**: Backward-incompatible principle removals, architectural shifts, or governance redefinitions.
- **MINOR**: Addition of new principles, new quality sections, or materially expanded integration standards.
- **PATCH**: Wording improvements, clarifications, and non-semantic corrections.

**Version**: 1.0.0 | **Ratified**: 2026-09-04 | **Last Amended**: 2026-09-04
