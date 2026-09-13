# Research: Pre-Commit Quality Hooks and Multi-Target CI/CD Publishing Pipeline

**Feature Branch**: `008-precommit-cicd-publishing`
**Date**: 2026-09-13
**Spec**: [spec.md](spec.md)

---

## 1. Pre-Commit Hooks Architecture

### Decision
Use a standard `.pre-commit-config.yaml` file leveraging upstream pre-commit hooks for file hygiene, Astral's `ruff-pre-commit` for linting and formatting, and a local `language: system` hook for running `pytest` using the active virtual environment (`.venv`).

### Rationale
- **Speed and Zero Installation Overhead**: Media-Cron already uses `ruff` (configured in `ruff.toml`) and `pytest` with dependencies like `tinytag`, `typer`, `pyyaml`, and `pytest-mock`. Running `pytest` under `language: python` inside pre-commit would force pre-commit to maintain an isolated virtualenv, repeatedly installing large dependencies whenever hooks update. `language: system` directly invokes `pytest` within the developer's local environment instantly.
- **Unified Formatting & Linting**: Using `astral-sh/ruff-pre-commit` ensures exact alignment between local CLI `ruff check / ruff format` and automated git pre-commit checks.
- **Hygiene Protection**: Upstream `pre-commit/pre-commit-hooks` provides battle-tested checks for trailing whitespace, end-of-file newlines, large file additions, and YAML/TOML syntax validation.

### Alternatives Considered
- *`language: python` for pytest*: Rejected due to high disk usage and slow pre-commit environment initialization.
- *Separate flake8 / black / isort hooks*: Rejected because the project already adopted `ruff` as the single fast tool for both linting and formatting.

---

## 2. Containerization & Multi-Architecture Strategy

### Decision
Create a multi-stage `Dockerfile` with `python:3.11-slim` as the base image. Set up a dedicated non-root user (`appuser`, UID/GID 10001), define standard media and configuration mount points (`/data`, `/config`, `/cache`), and designate `media-cron` as the entry point.
- **CI / Pull Requests**: Build for single architecture (`linux/amd64`) without pushing.
- **Release Tags (`v*.*.*`)**: Build multi-architecture (`linux/amd64` and `linux/arm64`) using Docker Buildx and QEMU, publishing to GitHub Container Registry (`ghcr.io/${{ github.repository }}`).

### Rationale
- **Security**: Running as non-root UID 10001 conforms to cloud-native best practices (Constitution Principle V) and Kubernetes security policies (`runAsNonRoot: true`).
- **Minimal Image Size**: `python:3.11-slim` yields a compressed container image well under 120 MB (meeting SC-004's requirement of <250 MB). Multi-stage build separates build tools from the final runtime image.
- **CI Build Performance**: QEMU-emulated ARM64 builds take 5–10x longer than native AMD64 builds. By limiting multi-arch builds strictly to official release tags, normal PR checks complete in under 2 minutes.

### Alternatives Considered
- *Alpine Linux Base (`python:3.11-alpine`)*: Rejected because Alpine uses `musl` libc, which frequently causes issues with audio metadata libraries and wheel binary compatibility compared to `slim` (`glibc`).
- *Multi-arch on every push*: Rejected to avoid wasting GitHub Actions runner minutes and delaying PR feedback.

---

## 3. Helm Chart Workload Architecture

### Decision
Design a Kubernetes Helm chart (`charts/media-cron/`) with configurable workload types:
- Default: `workloadType: "CronJob"` with configurable `cronjob.schedule` (defaulting to `"0 2 * * *"`).
- Alternative: `workloadType: "Deployment"` for continuous daemon execution.
Provide unified templates for PVC volume mounts (`/data`, `/config`, `/cache`), ConfigMap mounting for `config.yaml`, Secret environment variable injection, and standard Kubernetes security contexts.
Publish the chart as an OCI artifact to `oci://ghcr.io/${{ github.repository_owner }}/charts/media-cron` on release.

### Rationale
- **Operational Fit**: Media-Cron's core purpose is periodic batch organization and sanitation of media files. `CronJob` is the natural Kubernetes abstraction for scheduled batch executions. However, supporting `Deployment` ensures users running continuous background monitoring or daemon plugins can deploy the exact same chart.
- **OCI Standard**: Helm v3 natively supports OCI registries. Using `ghcr.io` allows hosting container images and Helm charts in the exact same registry under standard repository `GITHUB_TOKEN` credentials, eliminating the need for GitHub Pages or third-party chart repositories.

### Alternatives Considered
- *Dedicated Helm repository via GitHub Pages (`chart-releaser`)*: Rejected because OCI publishing to GHCR is standard in Helm 3, requires zero extra branches, and consolidates all OCI artifacts into one registry.
- *CronJob-only chart*: Rejected in favor of the clarified configurable workload pattern to allow flexible deployment modes.

---

## 4. Python Package Build & Release Strategy

### Decision
Use standard `build` (`python -m build`) to generate standard source distribution archives (`.tar.gz`) and binary wheels (`.whl`). Validate packaging integrity using `twine check`. On release tag push, upload both `.whl` and `.tar.gz` artifacts directly to the GitHub Release.

### Rationale
- **Zero Third-Party Credentials**: Distributing wheels and source archives directly on GitHub Releases satisfies User Story 3 without requiring external PyPI API tokens or Trusted Publisher setups. Users and automation can install releases directly with `pip install https://github.com/.../media_cron-*.whl`.
- **Packaging Standard**: `pyproject.toml` is already configured with `setuptools.build_meta`. `build` is the PEP 517 standard frontend.

### Alternatives Considered
- *Publishing to PyPI*: Deferred to post-release configuration if the user chooses to configure trusted publishing. Attaching packages to GitHub Releases is immediately secure and requires no external credentials.

---

## 5. GitHub Actions Workflow Architecture & Security

### Decision
Create two distinct GitHub Actions workflows in `.github/workflows/`:
1. **`ci.yml`** (Validation Gate):
   - Triggers: `push` on `main`, `pull_request` on `main`.
   - Permissions: `contents: read`.
   - Jobs:
     - `lint-and-test`: Matrix on Python 3.11 and 3.12 (ruff lint, ruff format check, pytest).
     - `container-validate`: Docker build for `linux/amd64` (dry-run, no push).
     - `helm-validate`: Helm lint on `charts/media-cron/`.
     - `package-validate`: Build `sdist` + `wheel` and verify with `twine check`.
2. **`release.yml`** (Publication Pipeline):
   - Triggers: `push` on `tags: ['v*.*.*']`.
   - Permissions: `contents: write` (for release assets), `packages: write` (for GHCR).
   - Jobs:
     - `test`: Pre-release gate ensuring full test suite passes.
     - `publish-container`: Multi-arch build (`amd64`, `arm64`) pushed to `ghcr.io/${{ github.repository }}`.
     - `publish-helm`: Helm package and OCI push to `oci://ghcr.io/${{ github.repository_owner }}/charts`.
     - `publish-python`: Build distribution packages, validate with twine, and upload to the GitHub Release via `gh release upload` or `softprops/action-gh-release`.

### Rationale
- **Least Privilege**: `ci.yml` runs with strictly read-only permissions, preventing any accidental or malicious publication from untrusted pull requests.
- **Failure Isolation**: Each publishing target runs in an independent job dependent on the test verification gate. If one job encounters an intermittent issue, others can succeed or be re-run independently.
