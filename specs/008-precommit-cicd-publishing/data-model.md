# Data Model: Pre-Commit Quality Hooks and Multi-Target CI/CD Publishing Pipeline

**Feature Branch**: `008-precommit-cicd-publishing`
**Date**: 2026-09-13
**Spec**: [spec.md](spec.md)

---

## 1. Key Entities & Schema Models

### Entity 1: PreCommitHookSet (`.pre-commit-config.yaml`)

Defines the local developer quality gate executed before commits are finalized.

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: check-added-large-files
        args: ['--maxkb=500']
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.4
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: pytest
        language: system
        pass_filenames: false
        always_run: true
```

#### Fields & Attributes
- `repos`: List of hook repository configurations.
  - `repo`: Repository URI or `local` for system executables.
  - `rev`: Git tag or release revision for external hooks.
  - `hooks`: List of individual hook definitions.
    - `id`: Unique identifier for the hook.
    - `name`: Human-readable display label.
    - `entry`: Executable command invoked.
    - `language`: Runtime environment (`system` for locally installed pytest in active virtualenv).
    - `pass_filenames`: Boolean; `false` when running repository-wide test runner.
    - `always_run`: Boolean; `true` to guarantee execution regardless of modified files.

---

### Entity 2: ContainerArtifact (`Dockerfile` & OCI Image)

Represents the OCI-compliant container image packaging Media-Cron for server and container runtimes.

#### Container Build Model
| Layer / Stage | Base Image / Target | Responsibility |
|---|---|---|
| **Builder Stage** | `python:3.11-slim` | Install build backend (`build`, `wheel`), build wheel from repository |
| **Runtime Stage** | `python:3.11-slim` | Minimal runtime, non-root user creation, package installation, runtime mounts |

#### Container Attributes
- **Base Image**: `python:3.11-slim` (Debian-based, glibc, minimal footprint <120 MB compressed).
- **Runtime User**: `appuser` (UID: `10001`, GID: `10001`, non-login shell `/sbin/nologin`).
- **Standard Mount Directories**:
  - `/data`: Media library, downloads, and staging directories.
  - `/config`: Configuration file (`config.yaml`).
  - `/cache`: Working directory for lockfiles, caches, and quarantine.
- **Environment Variables**:
  - `MEDIA_CRON_CONFIG`: `/config/config.yaml`
  - `PYTHONUNBUFFERED`: `1`
  - `PATH`: `/home/appuser/.local/bin:$PATH`
- **Default Entrypoint**: `["media-cron"]`
- **Default Command**: `["--help"]`
- **OCI Labels**:
  - `org.opencontainers.image.title`: `media-cron`
  - `org.opencontainers.image.description`: `Pluggable media file organizer, sanitizer, and cleaner CLI`
  - `org.opencontainers.image.source`: `https://github.com/<owner>/media-cron`
  - `org.opencontainers.image.licenses`: `MIT`

---

### Entity 3: HelmChartPackage (`charts/media-cron/`)

Represents the versioned Kubernetes deployment package.

#### Chart Metadata (`Chart.yaml`)
```yaml
apiVersion: v2
name: media-cron
description: Pluggable media file organizer, sanitizer, and cleaner Kubernetes chart
type: application
version: 0.1.0
appVersion: "0.1.0"
keywords:
  - media
  - cleaner
  - cron
  - torrent
home: https://github.com/pirish/media-cron
sources:
  - https://github.com/pirish/media-cron
```

#### Values Schema (`values.yaml`)
```yaml
workloadType: CronJob # "CronJob" or "Deployment"

image:
  repository: ghcr.io/pirish/media-cron
  pullPolicy: IfNotPresent
  tag: "" # Defaults to chart appVersion

imagePullSecrets: []
nameOverride: ""
fullnameOverride: ""

cronjob:
  schedule: "0 2 * * *"
  concurrencyPolicy: Forbid
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 1
  restartPolicy: OnFailure
  startingDeadlineSeconds: 600

deployment:
  replicaCount: 1
  strategy:
    type: Recreate

serviceAccount:
  create: true
  name: ""

podSecurityContext:
  runAsUser: 10001
  runAsGroup: 10001
  fsGroup: 10001

securityContext:
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: false
  capabilities:
    drop:
      - ALL

env: []
# - name: MEDIA_CRON_DRY_RUN
#   value: "false"

envFromSecret: "" # Optional Secret name containing credentials / API keys

persistence:
  data:
    enabled: true
    existingClaim: ""
    mountPath: /data
    accessMode: ReadWriteMany
    size: 500Gi
  config:
    enabled: false
    existingClaim: ""
    mountPath: /config
  cache:
    enabled: true
    existingClaim: ""
    mountPath: /cache
    accessMode: ReadWriteOnce
    size: 10Gi

resources:
  limits:
    cpu: 1000m
    memory: 1Gi
  requests:
    cpu: 100m
    memory: 128Mi
```

---

### Entity 4: PythonDistributionPackage

Standard Python packaging assets built from `pyproject.toml`.

- **Source Distribution (`sdist`)**: `dist/media_cron-<version>.tar.gz` containing source code, docs, and metadata.
- **Binary Wheel (`bdist_wheel`)**: `dist/media_cron-<version>-py3-none-any.whl` containing pre-built pure-python wheel.
- **Validation**: Verified with `twine check --strict dist/*` ensuring README renders correctly and metadata fields comply with PEP standards.

---

### Entity 5: PublishingPipeline (GitHub Actions Models)

#### CI Pipeline Model (`.github/workflows/ci.yml`)
- **Event**: `pull_request` (main), `push` (main)
- **Permissions**: `contents: read`
- **Job Matrix**:
  - `lint-and-test`: Python 3.11, 3.12 runners.
  - `container-build`: Validates Dockerfile build for `linux/amd64`.
  - `helm-lint`: Validates Helm chart structure and templating.
  - `package-build`: Validates `sdist`/`wheel` creation and `twine check`.

#### Release Pipeline Model (`.github/workflows/release.yml`)
- **Event**: `push: tags: ['v*.*.*']`
- **Permissions**: `contents: write`, `packages: write`
- **Job Dependency Graph**:
  ```mermaid
  graph TD
    Test[test-gate: lint & pytest] --> Container[publish-container: ghcr.io multi-arch]
    Test --> Helm[publish-helm: ghcr.io OCI chart]
    Test --> Python[publish-python: GitHub Release assets]
  ```
- **Targets**:
  1. `ghcr.io/${{ github.repository }}`: OCI container tagged with semver (`vX.Y.Z`), minor (`vX.Y`), major (`vX`), and `latest`.
  2. `oci://ghcr.io/${{ github.repository_owner }}/charts/media-cron`: Packaged Helm chart matching semver.
  3. GitHub Release: Release assets `.whl` and `.tar.gz` uploaded via `gh release upload`.
