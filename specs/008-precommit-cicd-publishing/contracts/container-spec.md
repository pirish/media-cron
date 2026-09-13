# Contract: Container Image Specification & Dockerfile

**Feature Branch**: `008-precommit-cicd-publishing`
**Date**: 2026-09-13
**Spec**: [spec.md](../spec.md)

---

## 1. Scope & Location

- **Dockerfile**: `Dockerfile` in the repository root.
- **Dockerignore**: `.dockerignore` in the repository root.

---

## 2. Multi-Stage Dockerfile Contract

### 2.1 Stage 1: Builder (`python:3.11-slim`)
- Installs `build` tools and wheel compiler dependencies.
- Copies project metadata (`pyproject.toml`, `README.md`) and package code (`media_cron/`).
- Runs `python -m build --wheel --outdir /dist`.
- Generates a standalone binary wheel package (`.whl`).

### 2.2 Stage 2: Final Runtime (`python:3.11-slim`)
- Minimal Debian slim base with essential runtime packages.
- Creates dedicated non-root user and group:
  - Username: `appuser`
  - Group: `appuser`
  - UID: `10001`
  - GID: `10001`
  - Home: `/home/appuser`
  - Shell: `/sbin/nologin`
- Copies built `.whl` from Stage 1 into the runtime stage.
- Installs the wheel into system/user Python environment via `pip install --no-cache-dir /dist/*.whl`.
- Creates standard runtime volume mount points with ownership set to `10001:10001`:
  - `/data` (Media libraries, staging directories, torrent downloads)
  - `/config` (Default configuration files)
  - `/cache` (Locks, transient state, review quarantine)
- Switches execution context to user `10001:10001`.
- Sets working directory to `/data`.
- Entrypoint: `["media-cron"]`.
- Default CMD: `["--help"]`.

---

## 3. Image Tags & Registry Contract

- **Registry**: GitHub Container Registry (`ghcr.io`).
- **Image Name**: `ghcr.io/<owner>/media-cron`.
- **Architectures**:
  - CI Builds: `linux/amd64` (validation only, no push).
  - Release Builds: `linux/amd64`, `linux/arm64` (multi-arch manifest pushed via Docker Buildx).
- **Tagging Rules**:
  - Release Tag `v1.2.3` generates:
    - `ghcr.io/<owner>/media-cron:1.2.3`
    - `ghcr.io/<owner>/media-cron:1.2`
    - `ghcr.io/<owner>/media-cron:1`
    - `ghcr.io/<owner>/media-cron:latest`
  - Non-release tags (e.g. `v1.2.3-rc1`) do not receive `latest`.

---

## 4. Environment & Volume Contracts

| Mount Point | Purpose | Typical Kubernetes Source | Permissions |
|---|---|---|---|
| `/data` | Input staging & organized libraries | PVC (`ReadWriteMany` or hostPath) | Read/Write (`10001:10001`) |
| `/config` | Declarative YAML configuration | ConfigMap or PVC | Read-Only or Read/Write |
| `/cache` | History database, lockfiles, review staging | PVC (`ReadWriteOnce`) or emptyDir | Read/Write (`10001:10001`) |

| Environment Variable | Default Value | Description |
|---|---|---|
| `MEDIA_CRON_CONFIG` | `/config/config.yaml` | Path to active configuration file |
| `PYTHONUNBUFFERED` | `1` | Forces unbuffered stdout/stderr for real-time logging |
| `MEDIA_CRON_LOG_LEVEL` | `INFO` | Logging verbosity |
