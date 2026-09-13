# Feature Specification: Pre-Commit Quality Hooks and Multi-Target CI/CD Publishing Pipeline

**Feature Branch**: `008-precommit-cicd-publishing`
**Created**: 2026-09-13
**Status**: Draft
**Input**: User description: "add precommit hooks with standard python checks. Precommit should also run the full test suite. Add GitHub action workflow to build and publish docker images and helm charts. Gha should also publish a python package as well."

---

## Clarifications

### Session 2026-09-13
- Q: What target CPU architectures should the GitHub Actions workflow build for the Media-Cron Docker container image? → A: Build linux/amd64 on all pushes, but build multi-arch (amd64 + arm64) only on release tags.
- Q: Where should the GitHub Actions release workflow publish the Python distribution packages (wheel and sdist)? → A: Publish wheels and source tarballs strictly to GitHub Releases (no external PyPI credentials needed).
- Q: How and where should the release workflow publish the packaged Helm chart? → A: Publish the Helm chart as an OCI artifact to GitHub Container Registry (oci://ghcr.io/<owner>/charts).
- Q: How should the pre-commit hook execute the full automated pytest suite? → A: Use language: system to run pytest via the active local virtual environment (fastest, reuses installed project dependencies).
- Q: What Kubernetes workload resource type should the Helm chart deploy by default? → A: Configurable via values, defaulting to CronJob with optional continuous Deployment mode.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Local Pre-Commit Quality & Test Gate (Priority: P1)

As a developer contributing to Media-Cron, I want automated git pre-commit hooks that format, lint, and run the complete test suite before any commit is finalized, so that broken code, style inconsistencies, and failing tests never enter the version history.

**Why this priority**: Local validation is the primary line of defense. Catching defects before they reach remote branches prevents broken main builds, protects Constitution Principle II (Test-First & Quality Gates), and ensures consistent code formatting across all contributions.

**Independent Test**: Install pre-commit hooks locally. Introduce a syntax/formatting error or a failing unit test, stage the change, and run `git commit`. Verify the commit is rejected with clear diagnostic output. Fix the issue and re-commit; verify the commit succeeds.

**Acceptance Scenarios**:

1. **Given** pre-commit hooks are installed in the repository, **When** a developer commits changes with unformatted code or style violations, **Then** pre-commit hooks automatically format the files or fail with actionable diagnostics, blocking the commit.
2. **Given** pre-commit hooks are installed, **When** a developer commits changes that cause any unit or integration test to fail, **Then** the test hook halts the commit process and reports failing test cases.
3. **Given** pre-commit hooks are installed, **When** all lint checks, formatting rules, hygiene checks (trailing whitespace, YAML/TOML syntax), and automated tests pass, **Then** the git commit completes cleanly.

---

### User Story 2 - Automated Container Image Build and Publication (Priority: P2)

As a DevOps engineer and container user, I want an automated GitHub Actions workflow that builds, tags, and publishes production-ready OCI-compliant container images to GitHub Container Registry whenever new releases or version tags are pushed, so that Media-Cron can be reliably deployed in containerized environments (Docker, Podman, Kubernetes).

**Why this priority**: Constitution Principle V mandates container-native deployment. Automating image creation and publishing ensures reproducible, isolated application runtimes are immediately accessible to end users without manual image assembly.

**Independent Test**: Trigger the container workflow via tag push or workflow dispatch in a test environment. Verify the container image is built, verified for basic executable entry-point sanity, and pushed to the target container registry with appropriate semantic version and `latest` tags.

**Acceptance Scenarios**:

1. **Given** a new version tag (e.g. `v0.2.0`) is pushed to the repository, **When** the continuous delivery workflow executes, **Then** a container image is built, tagged with both the semantic version and `latest`, and published to the container registry.
2. **Given** a pull request or non-tag push to `main`, **When** the workflow executes, **Then** the container image build is validated as a test step without publishing release tags to the public registry.
3. **Given** the published container image, **When** executed with `media-cron --help`, **Then** the container starts successfully and outputs CLI usage instructions.

---

### User Story 3 - Python Package Distribution & Publishing (Priority: P3)

As a Python developer or systems administrator, I want an automated GitHub Actions workflow that builds source distributions and binary wheels and publishes them to package repositories upon release, so that Media-Cron can be installed and updated cleanly via standard Python package managers (`pip`, `uv`, `pipx`).

**Why this priority**: Constitution Principle I mandates a Library-First and CLI-driven architecture. Distributing reusable Python packages enables both standalone CLI execution and programmatic integration as an importable library.

**Independent Test**: Trigger the package build workflow. Verify that standard source archives (`.tar.gz`) and binary wheels (`.whl`) are generated, validated with package hygiene checks, and uploaded to the distribution repository or release artifacts.

**Acceptance Scenarios**:

1. **Given** a tagged release, **When** the publishing workflow runs, **Then** compliant source distribution (`sdist`) and wheel (`bdist_wheel`) packages are generated.
2. **Given** generated distribution packages, **When** validation checks run, **Then** metadata, long description rendering, and dependency specifications are verified before upload.
3. **Given** verified distribution archives, **When** the release pipeline executes, **Then** packages are attached directly as downloadable assets to the GitHub Release.

---

### User Story 4 - Kubernetes Helm Chart Packaging and Distribution (Priority: P4)

As a Kubernetes cluster administrator, I want automated packaging and distribution of the Media-Cron Helm chart, so that scheduled cron jobs and daemon workflows can be deployed, configured, and upgraded using standard cloud-native deployment tools.

**Why this priority**: Media-Cron runs primarily as scheduled batch jobs and background cleaners. Helm packaging standardizes volume mounts, secret injection, and cron schedule definitions for cloud-native infrastructure.

**Independent Test**: Package the Helm chart via the packaging script/workflow. Verify the chart archive passes linting (`helm lint`), dependencies are resolved, and the packaged chart artifact is published to the chart repository or OCI registry.

**Acceptance Scenarios**:

1. **Given** changes to the Helm chart and a release tag, **When** the publishing workflow runs, **Then** the chart is linted, packaged, and published as an OCI artifact to `ghcr.io` with matching application and chart version metadata.
2. **Given** a published chart, **When** rendered using `helm template`, **Then** valid Kubernetes manifests for cron schedules, volumes, and environment configurations are generated.
3. **Given** default Helm chart configuration, **When** deployed or templated, **Then** a Kubernetes `CronJob` resource is created; **When** configured for continuous execution (`workloadType: Deployment`), **Then** a Kubernetes `Deployment` resource is created instead.

---

### Edge Cases

- **Emergency local commits**: Developers must retain the native git capability to bypass pre-commit hooks (`--no-verify`) during isolated work-in-progress rebases, while remote CI still strictly enforces checks before merge.
- **Pre-commit test execution time**: Running the entire test suite on every small commit could slow development; pre-commit test hooks must run cleanly and concisely in local virtual environments without hangs.
- **Workflow failure isolation**: If one publishing target fails (e.g., temporary PyPI outage), unaffected build steps (e.g., container build) should complete their validation or allow independent re-runs.
- **Release tag version alignment**: When a release tag (e.g., `v1.2.0`) triggers publishing, package metadata, container tags, and Helm chart versions must maintain consistency without manual multi-file edits.
- **Pull Request safety**: Workflows triggered by pull requests from forks or internal branches must execute test and build validations, but MUST NOT attempt credentialed publishing to package/container registries.

---

## Requirements *(mandatory)*

### Functional Requirements

#### Pre-Commit Quality Gate
- **FR-001**: The repository MUST provide a pre-commit configuration file (`.pre-commit-config.yaml`) defining standard file hygiene hooks (trailing whitespace removal, end-of-file fixers, YAML syntax validation, TOML syntax validation, large file check).
- **FR-002**: The pre-commit configuration MUST enforce Python code formatting and linting rules consistent with the project's quality standards.
- **FR-003**: The pre-commit configuration MUST execute the full automated test suite using a system-level hook (`language: system` invoking `pytest`) against the active local virtual environment, blocking the commit if any test fails.
- **FR-004**: Pre-commit hooks MUST operate cleanly without re-installing isolated package environments on each run by leveraging system-level execution or cached pre-commit environments.

#### Continuous Integration (CI)
- **FR-005**: A GitHub Actions workflow MUST run on all pull requests and pushes to `main`.
- **FR-006**: The CI workflow MUST run code linting, formatting verification, and the full test suite across supported Python environments.
- **FR-007**: The CI workflow MUST fail and block pull request merging if any quality check or test fails.

#### Container Packaging & Distribution
- **FR-008**: The repository MUST provide an optimized, multi-stage `Dockerfile` creating a minimal, non-root runtime image for Media-Cron.
- **FR-009**: The GitHub Actions pipeline MUST build and verify `linux/amd64` container images on pull requests and regular pushes to `main` to ensure build stability without emulation overhead.
- **FR-010**: Upon publication of a version tag (e.g., `v*.*.*`), the workflow MUST build and publish multi-architecture container images (`linux/amd64` and `linux/arm64`) using Docker Buildx and QEMU to GitHub Container Registry (`ghcr.io`).
- **FR-011**: Published container images MUST be tagged with the semantic version, major/minor release tags, and `latest` (for stable releases).

#### Python Package Distribution
- **FR-012**: The GitHub Actions pipeline MUST build standard Python distribution archives (`sdist` and `wheel`) upon release.
- **FR-013**: The workflow MUST validate package metadata and archive integrity using standard package validation tooling before distribution.
- **FR-014**: Upon publication of a version tag, the workflow MUST publish and attach the verified distribution packages (`.tar.gz` and `.whl`) as downloadable assets to the corresponding GitHub Release without requiring external third-party package index credentials.

#### Helm Chart Packaging & Distribution
- **FR-015**: The repository MUST provide a deployable Helm chart supporting configurable Kubernetes workload types (defaulting to scheduled `CronJob`, with optional continuous `Deployment` mode), including PVC volume mounts, ConfigMaps, and Secret references.
- **FR-016**: The GitHub Actions pipeline MUST lint and package the Helm chart upon release, publishing the packaged chart as an OCI artifact to GitHub Container Registry (`oci://ghcr.io/<owner>/charts/media-cron`) with matching chart and application versions.

---

### Key Entities

- **PreCommitHookSet**: Local developer configuration defining linters, formatters, hygiene checks, and test runner hooks executed prior to git commit finalization.
- **ContainerArtifact**: OCI-compliant container image packaging Media-Cron CLI runtime, bundled dependencies, non-root user setup, and volume mount points.
- **PythonDistributionPackage**: Standardized source archive (`.tar.gz`) and wheel (`.whl`) packaging Media-Cron modules, CLI entry points, and dependency metadata.
- **HelmChartPackage**: Versioned Kubernetes package containing templates, value schemas, and manifests for deploying scheduled Media-Cron tasks.
- **PublishingPipeline**: Orchestrated GitHub Actions workflow handling validation, build matrix execution, and conditional publication across container, package, and chart registries.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of commits created with pre-commit enabled are validated against format, lint, and test suites before commit finalization.
- **SC-002**: 100% of pull requests and main pushes trigger automated CI, preventing merge of regressions or style deviations.
- **SC-003**: Release automation publishes container images, Python packages, and Helm charts within 10 minutes of release tag creation.
- **SC-004**: Container image size is minimized (under 250 MB compressed) and executes without root privileges.
- **SC-005**: Zero release packages are published without first passing the entire automated test suite.

---

## Assumptions

- **Registry Target**: Container images and Helm charts will be published to GitHub Packages / GitHub Container Registry (`ghcr.io`) using default repository authentication tokens (`GITHUB_TOKEN`), minimizing third-party credential dependencies.
- **Python Package Index**: Package distribution will utilize standard GitHub Releases assets and trusted PyPI publishing tokens where configured.
- **Base Container Architecture**: Initial container builds will target standard `linux/amd64` (and optionally `linux/arm64` via QEMU/Buildx).
- **Local Developer Prerequisites**: Developers are assumed to have Python 3.11+ and git installed locally; pre-commit installation will be documented in project developer guides.
