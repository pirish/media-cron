# Quickstart: Validating Pre-Commit Hooks and CI/CD Publishing Pipeline

**Feature Branch**: `008-precommit-cicd-publishing`
**Date**: 2026-09-13
**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

---

## Prerequisites

- **Python**: 3.11+ with active virtual environment (`.venv`)
- **Docker / Podman**: Engine running locally for container builds
- **Helm**: Helm v3 CLI installed (`helm version`)
- **Pre-Commit**: `pre-commit` CLI installed in virtualenv (`pip install pre-commit`)
- **Build Tools**: `build` and `twine` installed in virtualenv (`pip install build twine`)

---

## Validation Scenario 1: Local Pre-Commit Quality & Test Gate

### Objective
Verify that `.pre-commit-config.yaml` runs all file hygiene hooks, invokes `ruff` lint/format, and executes the complete `pytest` test suite against the local virtual environment.

### Steps

1. **Install hooks into local git repository**:
   ```bash
   pre-commit install
   ```
   *Expected Output*: `pre-commit installed at .git/hooks/pre-commit`

2. **Run all hooks manually against all files**:
   ```bash
   pre-commit run --all-files
   ```
   *Expected Outcome*:
   - `Trim Trailing Whitespace`: Passed
   - `Fix End of Files`: Passed
   - `Check YAML`: Passed
   - `Check TOML`: Passed
   - `Check Large Files`: Passed
   - `ruff`: Passed
   - `ruff-format`: Passed
   - `pytest`: Passed (all unit and integration tests passing)

3. **Verify commit gate blocks failing tests**:
   - Temporarily add an assertion failure in any test file.
   - Stage the change: `git add tests/`
   - Attempt commit: `git commit -m "test: intentional failure"`
   - *Expected Outcome*: Commit is rejected, pytest displays failure details.
   - Revert the temporary failure.

---

## Validation Scenario 2: Container Image Build & Non-Root Execution

### Objective
Verify that `Dockerfile` produces a minimal, non-root OCI container image that starts up cleanly and displays CLI help.

### Steps

1. **Build the container image**:
   ```bash
   docker build -t media-cron:test .
   ```
   *Expected Outcome*: Multi-stage build succeeds; wheel is built and installed into runtime image.

2. **Verify image size**:
   ```bash
   docker images media-cron:test --format "{{.Size}}"
   ```
   *Expected Outcome*: Image size is under 250 MB (typically <120 MB).

3. **Run non-root CLI sanity check**:
   ```bash
   docker run --rm media-cron:test --help
   ```
   *Expected Outcome*: Outputs `media-cron` CLI usage instructions; exits with code 0.

4. **Verify container user**:
   ```bash
   docker run --rm --entrypoint id media-cron:test
   ```
   *Expected Outcome*: `uid=10001(appuser) gid=10001(appuser) groups=10001(appuser)`

---

## Validation Scenario 3: Helm Chart Linting & Manifest Templating

### Objective
Verify that `charts/media-cron/` passes linting and correctly templates both `CronJob` and `Deployment` workloads.

### Steps

1. **Lint Helm chart**:
   ```bash
   helm lint charts/media-cron
   ```
   *Expected Outcome*: `1 chart(s) linted, 0 chart(s) failed`

2. **Template default CronJob workload**:
   ```bash
   helm template test-release charts/media-cron
   ```
   *Expected Outcome*: Generates a Kubernetes manifest with `kind: CronJob` containing schedule `0 2 * * *`.

3. **Template continuous Deployment workload**:
   ```bash
   helm template test-release charts/media-cron --set workloadType=Deployment
   ```
   *Expected Outcome*: Generates a Kubernetes manifest with `kind: Deployment` containing replicas and pod template.

---

## Validation Scenario 4: Python Package Build & Metadata Validation

### Objective
Verify that standard distribution packages (`.tar.gz` and `.whl`) build cleanly and satisfy PEP packaging standards.

### Steps

1. **Build distribution packages**:
   ```bash
   python -m build
   ```
   *Expected Outcome*: Creates `dist/media_cron-<version>.tar.gz` and `dist/media_cron-<version>-py3-none-any.whl`.

2. **Validate distribution package integrity**:
   ```bash
   twine check --strict dist/*
   ```
   *Expected Outcome*: `Checking dist/...: PASSED`

---

## Validation Scenario 5: GitHub Actions Workflows Syntax & Trigger Verification

### Objective
Verify that `.github/workflows/ci.yml` and `.github/workflows/release.yml` have valid YAML syntax and compliant trigger configurations.

### Steps

1. **Validate workflow YAML syntax**:
   ```bash
   python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); yaml.safe_load(open('.github/workflows/release.yml'))"
   ```
   *Expected Outcome*: Clean exit code 0.

2. **Check permissions & triggers**:
   - `ci.yml` triggers on `pull_request` and `push` to `main`, with permissions `contents: read`.
   - `release.yml` triggers on `push` tags `v*.*.*`, with permissions `contents: write` and `packages: write`.
