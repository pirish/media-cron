# Configuration Schema: Audiobook Identification & Providers

**Branch**: `003-audiobook-identification` | **Date**: 2026-09-08 | **Spec**: [spec.md](../spec.md)

## 1. YAML Configuration Schema

Added under top-level `audiobook` key in `config.yaml`:

```yaml
audiobook:
  # Enable or disable external lookup queries entirely (local-only if false)
  enable_external_lookup: true

  # Minimum confidence threshold (0.0 to 1.0) required to override local author/title
  confidence_threshold: 0.85

  # Persistent response cache settings
  cache:
    enabled: true
    ttl_seconds: 2592000          # 30 days
    cache_file: ".media-cron-cache/audiobook_cache.json"

  # Ordered list of external metadata service providers
  providers:
    openlibrary:
      enabled: true
      priority: 10
      base_url: "https://openlibrary.org"
      timeout_seconds: 5.0
      rate_limit_delay: 1.0

    audnexus:
      enabled: false              # Disabled by default, easily enabled
      priority: 20
      base_url: "https://api.audnexus.com"
      timeout_seconds: 5.0
      rate_limit_delay: 0.5
```

---

## 2. Environment Variable Overrides

Environment variables override values loaded from `config.yaml`:

| Environment Variable | Target Configuration Key | Default Value | Description |
|---|---|---|---|
| `MEDIA_CRON_AUDIOBOOK_ENABLE_LOOKUP` | `audiobook.enable_external_lookup` | `"true"` | `"true"` or `"false"` to toggle external queries |
| `MEDIA_CRON_AUDIOBOOK_CONFIDENCE_THRESHOLD` | `audiobook.confidence_threshold` | `"0.85"` | Float string threshold $[0.0, 1.0]$ |
| `MEDIA_CRON_AUDIOBOOK_CACHE_ENABLED` | `audiobook.cache.enabled` | `"true"` | Toggle persistent response caching |
| `MEDIA_CRON_AUDIOBOOK_CACHE_TTL` | `audiobook.cache.ttl_seconds` | `"2592000"` | Cache TTL in seconds |
| `MEDIA_CRON_AUDIOBOOK_CACHE_FILE` | `audiobook.cache.cache_file` | `".media-cron-cache/audiobook_cache.json"` | Path to JSON cache file |
| `MEDIA_CRON_OPENLIBRARY_ENABLED` | `audiobook.providers.openlibrary.enabled` | `"true"` | Enable Open Library provider |
| `MEDIA_CRON_AUDNEXUS_ENABLED` | `audiobook.providers.audnexus.enabled` | `"false"` | Enable Audnexus provider |
| `MEDIA_CRON_OPENLIBRARY_TIMEOUT` | `audiobook.providers.openlibrary.timeout_seconds` | `"5.0"` | Open Library timeout in seconds |
| `MEDIA_CRON_AUDNEXUS_TIMEOUT` | `audiobook.providers.audnexus.timeout_seconds` | `"5.0"` | Audnexus timeout in seconds |
