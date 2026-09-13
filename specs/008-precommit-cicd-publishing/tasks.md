# Tasks: Pre-Commit Quality Hooks and Multi-Target CI/CD Publishing Pipeline

**Feature**: `008-precommit-cicd-publishing`
**Input**: Design artifacts from `specs/008-precommit-cicd-publishing/` (`spec.md`, `plan.md`, `data-model.md`, `contracts/`, `quickstart.md`)
**Status**: Ready for Implementation

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, dependency management, and directory scaffolding.

- [X] T001 Update `pyproject.toml` dev dependencies to include `pre-commit`, `build`, and `twine` in pyproject.toml
- [X] T002 [P] Create container ignore rules in .dockerignore
- [X] T003 [P] Create GitHub Actions workflows directory structure in .github/workflows/
- [X] T004 [P] Create Helm chart directory structure in charts/media-cron/templates/

---

## Phase 2: Foundational (Workflow Schemas & Validation Framework)

**Purpose**: Core GitHub Actions workflow definitions and workflow verification tests that all distribution targets rely upon.

**⚠️ CRITICAL**: Workflow foundations MUST be established before story-specific CI/CD integration.

- [X] T005 [P] Author unit tests for GitHub Actions workflow definitions and permission models in tests/unit/test_github_workflows.py
- [X] T006 [P] Implement base CI workflow definition for PR and push verification across Python 3.11/3.12 in .github/workflows/ci.yml
- [X] T007 [P] Implement base Release workflow definition with test-gate for version tags in .github/workflows/release.yml

**Checkpoint**: Shared infrastructure and base CI/CD pipelines created and test-validated.

---

## Phase 3: User Story 1 - Local Pre-Commit Quality & Test Gate (Priority: P1) 🎯 MVP

**Goal**: Configure and enforce automated local git pre-commit hooks for file hygiene, ruff lint/formatting, and full test suite execution (`pytest`) using a system-level hook.

**Independent Test**: Install hooks with `pre-commit install` and run `pre-commit run --all-files`. Verify file hygiene checks pass, ruff formatting and linting pass, and all pytest tests pass cleanly. Introduce a temporary assertion failure and verify pre-commit blocks the commit.

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T008 [P] [US1] Author unit tests verifying `.pre-commit-config.yaml` hook configurations, IDs, and system pytest parameters in tests/unit/test_precommit_config.py
- [X] T009 [P] [US1] Author integration tests verifying pre-commit hook execution behavior and exit code gating in tests/integration/test_precommit_hooks.py

### Implementation for User Story 1

- [X] T010 [US1] Create and configure `.pre-commit-config.yaml` with file hygiene, ruff, and system-level pytest hooks in .pre-commit-config.yaml
- [X] T011 [US1] Document pre-commit installation and developer workflow commands in README.md

**Checkpoint**: User Story 1 complete and independently testable (MVP delivery). Local commits are protected by automated quality gates.

---

## Phase 4: User Story 2 - Automated Container Image Build and Publication (Priority: P2)

**Goal**: Implement an optimized multi-stage `Dockerfile` with non-root security (UID 10001), standard mount points (`/data`, `/config`, `/cache`), and automated CI/CD container workflows for single-arch PR verification and multi-arch (`amd64` + `arm64`) publishing to GHCR.

**Independent Test**: Build the container image locally (`docker build -t media-cron:test .`) and verify execution with `docker run --rm media-cron:test --help`. Verify that `id` reports UID 10001 and image size is under 250 MB.

### Tests for User Story 2 ⚠️

- [X] T012 [P] [US2] Author unit tests for Dockerfile multi-stage structure, non-root user setup, volume targets, and .dockerignore rules in tests/unit/test_dockerfile.py
- [X] T013 [P] [US2] Author integration tests for container build sanity and CLI entry point invocation in tests/integration/test_container_packaging.py

### Implementation for User Story 2

- [X] T014 [US2] Implement multi-stage `Dockerfile` with non-root user `appuser` (UID 10001) and volume mounts in Dockerfile
- [X] T015 [US2] Wire container build validation job (`container-validate` for `linux/amd64`) into .github/workflows/ci.yml
- [X] T016 [US2] Wire multi-arch container publish job (`publish-container` for `linux/amd64` and `linux/arm64` to `ghcr.io`) into .github/workflows/release.yml

**Checkpoint**: User Stories 1 and 2 complete. Container packaging is verified and integrated into CI/CD.

---

## Phase 5: User Story 3 - Python Package Distribution & Publishing (Priority: P3)

**Goal**: Provide automated building of source distributions (`.tar.gz`) and binary wheels (`.whl`), metadata validation via `twine check`, and release asset uploads directly to GitHub Releases.

**Independent Test**: Run `python -m build` followed by `twine check --strict dist/*` locally. Verify that valid `.whl` and `.tar.gz` archives are generated without warnings.

### Tests for User Story 3 ⚠️

- [X] T017 [P] [US3] Author integration tests for package build and twine metadata validation in tests/integration/test_package_distribution.py

### Implementation for User Story 3

- [X] T018 [US3] Wire package build and validation job (`package-validate` with `build` and `twine check`) into .github/workflows/ci.yml
- [X] T019 [US3] Wire package release asset publication job (`publish-python` uploading `.whl` and `.tar.gz` to GitHub Releases) into .github/workflows/release.yml

**Checkpoint**: User Stories 1, 2, and 3 complete. Python distribution packages are validated in CI and attached to releases.

---

## Phase 6: User Story 4 - Kubernetes Helm Chart Packaging and Distribution (Priority: P4)

**Goal**: Deliver a production-ready Kubernetes Helm chart (`charts/media-cron/`) supporting configurable workloads (defaulting to `CronJob`, with optional continuous `Deployment` mode), PVC volume mounts, and automated OCI chart publication to GHCR.

**Independent Test**: Run `helm lint charts/media-cron`. Render manifests using `helm template` under default values (verifying `CronJob` resource) and with `--set workloadType=Deployment` (verifying `Deployment` resource).

### Tests for User Story 4 ⚠️

- [X] T020 [P] [US4] Author unit tests for Helm chart metadata, values schema, and YAML syntax in tests/unit/test_helm_chart_files.py
- [X] T021 [P] [US4] Author integration tests for Helm template rendering and workload mode switching in tests/integration/test_helm_chart.py

### Implementation for User Story 4

- [X] T022 [P] [US4] Implement `Chart.yaml` and default `values.yaml` in charts/media-cron/Chart.yaml and charts/media-cron/values.yaml
- [X] T023 [P] [US4] Implement template helpers and ServiceAccount manifest in charts/media-cron/templates/_helpers.tpl and charts/media-cron/templates/serviceaccount.yaml
- [X] T024 [P] [US4] Implement CronJob and Deployment workload templates in charts/media-cron/templates/cronjob.yaml and charts/media-cron/templates/deployment.yaml
- [X] T025 [P] [US4] Implement ConfigMap and PVC persistence templates in charts/media-cron/templates/configmap.yaml and charts/media-cron/templates/pvc.yaml
- [X] T026 [US4] Wire Helm lint validation job (`helm-validate`) into .github/workflows/ci.yml
- [X] T027 [US4] Wire Helm OCI package and publish job (`publish-helm` to `oci://ghcr.io/<owner>/charts`) into .github/workflows/release.yml

**Checkpoint**: All 4 user stories complete. Pre-commit hooks, Docker images, Python packages, and Helm charts are fully automated.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: End-to-end quickstart validation, documentation updates, and repository quality gate verification.

- [X] T028 [P] Author integration tests verifying end-to-end quickstart scenarios 1-5 in tests/integration/test_cicd_quickstart.py
- [X] T029 [P] Update developer and deployment documentation in README.md
- [X] T030 Execute pre-commit validation across all repository files using pre-commit run --all-files
- [X] T031 Run complete test suite and code quality gates via pytest, ruff check ., and ruff format .

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Story 1 (Phase 3)**: Can start after Foundational (Phase 2) - Delivers MVP local quality gate
- **User Story 2 (Phase 4)**: Can start after Foundational (Phase 2) - Delivers container packaging
- **User Story 3 (Phase 5)**: Can start after Foundational (Phase 2) - Delivers Python package distribution
- **User Story 4 (Phase 6)**: Can start after Foundational (Phase 2) - Delivers Helm chart deployment
- **Polish (Phase 7)**: Depends on all user stories (Phases 3-6) being complete

### User Story Dependencies

- **User Story 1 (P1)**: Independent of US2, US3, and US4. Focuses on local developer environment and git hooks.
- **User Story 2 (P2)**: Independent of US3 and US4. Relies on existing `media_cron` package.
- **User Story 3 (P3)**: Independent of US2 and US4. Relies on existing `pyproject.toml`.
- **User Story 4 (P4)**: Relies on container image name/tag contracts established in US2, but manifests can be authored in parallel.

### Parallel Opportunities

- **Phase 1**: T002, T003, T004 can execute in parallel once T001 is started.
- **Phase 2**: T005, T006, T007 can all run in parallel.
- **Phase 3 (US1)**: Test tasks T008 and T009 can run in parallel before implementation.
- **Phase 4 (US2)**: Test tasks T012 and T013 can run in parallel before implementation.
- **Phase 5 (US3)**: Test task T017 can run in parallel before implementation.
- **Phase 6 (US4)**: Test tasks T020 and T021, and implementation tasks T022, T023, T024, T025 can all run in parallel.
- **Phase 7**: T028 and T029 can execute in parallel before final validation (T030, T031).

---

## Implementation Strategy

### MVP First (User Story 1 Only)
1. Complete Phase 1: Setup (`pyproject.toml`, directory structure).
2. Complete Phase 2: Foundational (base GitHub Actions workflows).
3. Complete Phase 3: User Story 1 (pre-commit configuration, pytest hook, developer documentation).
4. **STOP and VALIDATE**: Run `pre-commit run --all-files` and verify local commit protection.
5. Deployable MVP: All team commits and pull requests are locally guarded against errors.

### Incremental Delivery
1. Add User Story 2: Container image `Dockerfile` and automated single/multi-arch GHCR publishing.
2. Add User Story 3: Python package distribution archives (`.whl` and `.tar.gz`) uploaded to GitHub Releases.
3. Add User Story 4: Kubernetes Helm chart (`charts/media-cron/`) and automated OCI chart publication to GHCR.
4. Finalize with Phase 7: Quickstart validation scenarios 1-5, documentation updates, and repository quality gate verification.
