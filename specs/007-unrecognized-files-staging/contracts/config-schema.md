# Contract: Configuration Schema

**Scope**: Configuration definitions and environment bindings for unrecognized media staging and manual review.  

---

## 1. YAML Configuration Schema

```yaml
paths:
  source_dir: "/data/downloads"
  staging_dir: "/data/staging"
  destination_dir: "/data/media"
  review_dir: "/data/review"              # Path where unrecognized media items are staged

review:
  enabled: true                           # Enables automatic staging of unrecognized media when review_dir is set
  max_age_days: 0                         # Retention limit in days (0 = disabled / indefinite retention)
```

---

## 2. Environment Variable Bindings

| Environment Variable | YAML Path | Default | Description |
|---|---|---|---|
| `MEDIA_CRON_PATHS_REVIEW_DIR` | `paths.review_dir` | `null` | Absolute path to the review staging directory. |
| `MEDIA_CRON_REVIEW_ENABLED` | `review.enabled` | `true` | Enable or disable unrecognized media staging. |
| `MEDIA_CRON_REVIEW_MAX_AGE_DAYS` | `review.max_age_days` | `0` | Age threshold for review purge (0 = disabled). |

---

## 3. Precedence Rules

Configuration settings resolve in the following order (highest precedence first):
1. Explicit CLI arguments (`--review-dir`, `--review-max-age-days`).
2. Environment variables (`MEDIA_CRON_PATHS_REVIEW_DIR`, `MEDIA_CRON_REVIEW_MAX_AGE_DAYS`).
3. YAML configuration file (`media-cron.yml`).
4. Built-in defaults (`paths.review_dir = None`, `review.enabled = True`, `review.max_age_days = 0`).
