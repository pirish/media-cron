# Implementation Plan: Pre-Commit Quality Hooks and Multi-Target CI/CD Publishing Pipeline

**Branch**: `008-precommit-cicd-publishing` | **Date**: 2026-09-13 | **Spec**: [spec.md](spec.md)

---

## Summary

This feature establishes comprehensive automated quality gates and release distribution automation for Media-Cron across local and remote environments:

1. **Local Pre-Commit Quality Gate**: Configures `.pre-commit-config.yaml` to enforce file hygiene (trailing whitespace, end-of-file fixers, YAML/TOML validation, large file protection), fast code formatting and linting via Astral's `ruff-pre-commit`, and full automated test suite execution via a local virtual environment system hook (`language: system` invoking `pytest`).
2. **Container Packaging**: Implements an optimized multi-stage `Dockerfile` (built on `python:3.11-slim`) providing a secure non-root runtime environment (`appuser`, UID/GID 10001) under 120 MB compressed, with dedicated volume mounts (`/data`, `/config`, `/cache`) and `media-cron` entrypoint.
3. **Helm Chart Deployment**: Delivers a production-ready Kubernetes Helm chart (`charts/media-cron/`) supporting configurable workload modes (defaulting to scheduled `CronJob`, with optional continuous daemon `Deployment`), PVC persistence, ConfigMap mounts, and Secret injection.
4. **CI Validation Pipeline**: Introduces `.github/workflows/ci.yml` running on pull requests and pushes to `main`, validating multi-version Python compatibility (3.11, 3.12), linting/formatting, test suites, container build sanity (single-arch `amd64`), Helm chart linting, and packaging integrity.
5. **Multi-Target Release Pipeline**: Implements `.github/workflows/release.yml` triggered on version tags (`v*.*.*`), running test verification before publishing multi-architecture container images (`amd64` + `arm64`) to GitHub Container Registry (`ghcr.io`), publishing Helm charts as OCI artifacts to GHCR (`oci://ghcr.io/<owner>/charts`), and uploading distribution packages (`.whl` and `.tar.gz`) as downloadable assets to the GitHub Release.

---

## Technical Context

**Language/Version**: Python 3.11+ (tested on Python 3.11, 3.12, 3.13)
**Primary Dependencies**:
- Local Development: `pre-commit`, `ruff`, `pytest`, `build`, `twine`
- Application Runtime: existing `typer`, `pyyaml`, `tinytag` (zero new runtime dependencies added)
**Storage**: N/A for workflows/hooks; container and Helm chart define standard mount targets for `/data`, `/config`, and `/cache`.
**Testing**: `pytest` executed locally via pre-commit (`language: system`) and remotely in GitHub Actions across Python 3.11 and 3.12 matrices; `helm lint` and `twine check` for artifact validation.
**Target Platform**: Linux (bare-metal, Docker/Podman, Kubernetes CronJob/Deployment), GitHub Actions runners (`ubuntu-latest`).
**Project Type**: Python CLI utility, container image, and Kubernetes Helm chart.
**Performance Goals**:
- Pre-commit local test execution completes cleanly without re-downloading environments.
- CI pipeline completes in <3 minutes on PRs.
- Multi-arch release builds complete in <10 minutes on release tags.
- Container image size <120 MB compressed (well under 250 MB ceiling in SC-004).
**Constraints**:
- Constitution Principle II: Strict test-first and automated quality gate enforcement.
- Constitution Principle V: Non-root container security (`runAsNonRoot: true`, UID 10001) and declarative volume management.
- Zero external third-party registry secrets: distribution uses native GitHub capabilities (`GITHUB_TOKEN`, GHCR, and GitHub Releases assets).

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Principle I: Library-First & CLI-Driven**: **PASS**. The container image and packaging pipeline strictly wrap and expose the standalone `media_cron` Python library and CLI entry point without embedding business logic into workflow scripts.
- **Principle II: Test-First & Contract Verification (NON-NEGOTIABLE)**: **PASS**. The pre-commit hook halts commits immediately if any test fails. The CI workflow verifies tests on Python 3.11 and 3.12 before merging. The release workflow gates all publishing jobs behind successful test execution.
- **Principle III: Idempotency & Failure Resilience**: **PASS**. Container builds use multi-stage caching. Release publishing jobs are decoupled; failure in one target allows independent re-runs. Container tags and OCI charts use deterministic semantic versions.
- **Principle IV: Structured Observability & Diagnosability**: **PASS**. Pre-commit and CI runners emit clear diagnostic output on stderr. The Dockerfile sets `PYTHONUNBUFFERED=1` to ensure real-time structured log streaming in container environments.
- **Principle V: Container-Native & Environment Isolation**: **PASS**. Directly implements container-native deployment via multi-stage `Dockerfile` and Kubernetes Helm chart with declarative volume mounts and non-root security.

---

## Project Structure

### Documentation (this feature)

```text
specs/008-precommit-cicd-publishing/
├── plan.md                                      # This implementation plan
├── research.md                                  # Technical decisions and architectural rationale
├── data-model.md                                # Entities, schemas, values models, and workflow graphs
├── quickstart.md                                # 5 runnable validation scenarios
├── checklists/
│   └── requirements.md                          # Specification quality checklist
├── contracts/
│   ├── pre-commit-hooks.md                      # Pre-commit hook definitions, stages, and execution rules
│   ├── container-spec.md                        # Multi-stage Dockerfile, non-root user, and OCI tags
│   ├── helm-chart-spec.md                       # Helm chart templates, values schema, and OCI distribution
│   └── github-workflows.md                      # CI/CD workflows, triggers, permissions, and job graph
└── tasks.md                                     # Implementation tasks (generated by /speckit-tasks)
```

### Source Code (repository root)

```text
.
├── .pre-commit-config.yaml                      # Pre-commit hook configuration
├── Dockerfile                                   # Multi-stage container build definition
├── .dockerignore                                # Container build ignore rules
├── .github/
│   └── workflows/
│       ├── ci.yml                               # Continuous Integration workflow (PR & main)
│       └── release.yml                          # Multi-target release publishing workflow (tags)
├── charts/
│   └── media-cron/
│       ├── Chart.yaml                           # Helm chart metadata
│       ├── values.yaml                          # Default Helm configuration values
│       └── templates/
│           ├── _helpers.tpl                     # Chart template helpers
│           ├── cronjob.yaml                     # Kubernetes CronJob workload manifest
│           ├── deployment.yaml                  # Kubernetes Deployment workload manifest
│           ├── configmap.yaml                   # Optional application configuration ConfigMap
│           ├── pvc.yaml                         # Optional persistent volume claims
│           └── serviceaccount.yaml              # Pod service account manifest
├── media_cron/                                  # Existing Python library code
├── pyproject.toml                               # Python build system & dependency configuration
└── tests/                                       # Existing automated test suites
```

**Structure Decision**: Standard repository layout. Configuration files (`.pre-commit-config.yaml`, `Dockerfile`, `.dockerignore`) reside at repository root for tool convention; GitHub workflows reside in `.github/workflows/`; Helm chart files reside in `charts/media-cron/`.

---

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| *None* | All components use standard conventions (pre-commit, Dockerfile, Helm v3, GitHub Actions). | N/A |
