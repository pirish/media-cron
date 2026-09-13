# Contract: Helm Chart Specification

**Feature Branch**: `008-precommit-cicd-publishing`
**Date**: 2026-09-13
**Spec**: [spec.md](../spec.md)

---

## 1. Scope & Location

- **Chart Directory**: `charts/media-cron/`
- **Primary Files**:
  - `Chart.yaml`: Chart metadata and version bindings.
  - `values.yaml`: Default user-configurable parameters.
  - `templates/_helpers.tpl`: Template helper functions for standard labels and names.
  - `templates/cronjob.yaml`: Kubernetes `CronJob` manifest (active when `workloadType == "CronJob"`).
  - `templates/deployment.yaml`: Kubernetes `Deployment` manifest (active when `workloadType == "Deployment"`).
  - `templates/configmap.yaml`: Optional ConfigMap template for application configuration.
  - `templates/pvc.yaml`: Optional PersistentVolumeClaim templates for `/data` and `/cache`.
  - `templates/serviceaccount.yaml`: Optional ServiceAccount manifest.

---

## 2. Workload Type Contract

### 2.1 Mode A: CronJob (`workloadType: CronJob` - Default)
- Renders a `batch/v1` `CronJob` resource.
- **Spec Attributes**:
  - `schedule`: Controlled by `.Values.cronjob.schedule` (default: `"0 2 * * *"`).
  - `concurrencyPolicy`: Controlled by `.Values.cronjob.concurrencyPolicy` (default: `Forbid`).
  - `startingDeadlineSeconds`: Default `600`.
  - `restartPolicy`: Default `OnFailure`.
  - `successfulJobsHistoryLimit`: Default `3`.
  - `failedJobsHistoryLimit`: Default `1`.
- Container command runs one-off media organization batch, e.g. `["media-cron", "organize"]` or default arguments.

### 2.2 Mode B: Deployment (`workloadType: Deployment`)
- Renders an `apps/v1` `Deployment` resource.
- **Spec Attributes**:
  - `replicas`: Controlled by `.Values.deployment.replicaCount` (default: `1`).
  - `strategy`: Controlled by `.Values.deployment.strategy` (default: `type: Recreate` to avoid volume lock contention).
  - Container runs in continuous daemon or watch mode.

---

## 3. Storage & Volume Mount Contract

| Value Path | Mount Path | Purpose | Supported Configurations |
|---|---|---|---|
| `persistence.data` | `/data` | Media staging and organized libraries | `existingClaim`, or new PVC creation |
| `persistence.config` | `/config` | Optional YAML configuration file mount | `existingClaim`, ConfigMap, or emptyDir |
| `persistence.cache` | `/cache` | Transient lockfiles, quarantine, history | `existingClaim`, or new PVC creation |

---

## 4. OCI Packaging & Distribution Contract

- **Registry**: GitHub Container Registry (`ghcr.io`).
- **OCI Destination URI**: `oci://ghcr.io/<owner>/charts/media-cron`.
- **Packaging Command**:
  ```bash
  helm package charts/media-cron --version <version> --app-version <appVersion> -d dist/charts
  ```
- **Push Command**:
  ```bash
  helm push dist/charts/media-cron-<version>.tgz oci://ghcr.io/<owner>/charts
  ```
- **Verification**: `helm lint charts/media-cron` MUST pass with 0 errors before packaging.
