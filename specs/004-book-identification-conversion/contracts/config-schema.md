# Contract: Configuration Schema & Environment Variables

**Feature**: Book Identification, UDC Classification, and EPUB Conversion  
**Branch**: `004-book-identification-conversion`  
**Date**: 2026-09-09  

## 1. YAML Configuration Schema

Under the root configuration file (`media-cron.yml`):

```yaml
books:
  enabled: true
  enable_external_lookup: true
  confidence_threshold: 0.85
  
  udc_lookup:
    enabled: false                   # Opt-in by default
    min_confidence: 0.70
    summary_table_path: null         # null = use bundled udc_summary.json

  conversion:
    enabled: false                   # Opt-in by default
    preferred_engine: "calibre"      # "calibre" or "python_fallback"
    timeout_seconds: 120
    retention_policy: "preserve"     # "preserve", "archive", or "replace"
    archive_dir: null                # Required if retention_policy is "archive"
    inject_metadata: true            # Inject canonical tags & UDC into EPUB OPF

  cache:
    enabled: true
    cache_file: ".media-cron-cache/book_cache.json"
    ttl_seconds: 2592000             # 30 days default

  providers:
    openlibrary:
      enabled: true
      priority: 1
      endpoint: "https://openlibrary.org/search.json"
      timeout_seconds: 5.0
      rate_limit_delay: 0.5
```

---

## 2. Environment Variable Overrides

Environment variables override YAML settings (Constitution Principle V: Container-Native):

| Environment Variable | Type | Default | Maps To YAML Path |
|---|---|---|---|
| `MEDIA_CRON_BOOKS_ENABLED` | `bool` | `true` | `books.enabled` |
| `MEDIA_CRON_BOOKS_EXTERNAL_LOOKUP` | `bool` | `true` | `books.enable_external_lookup` |
| `MEDIA_CRON_BOOKS_CONFIDENCE_THRESHOLD` | `float` | `0.85` | `books.confidence_threshold` |
| `MEDIA_CRON_BOOKS_UDC_ENABLED` | `bool` | `false` | `books.udc_lookup.enabled` |
| `MEDIA_CRON_BOOKS_CONVERT_EPUB` | `bool` | `false` | `books.conversion.enabled` |
| `MEDIA_CRON_BOOKS_CONVERSION_ENGINE` | `str` | `"calibre"` | `books.conversion.preferred_engine` |
| `MEDIA_CRON_BOOKS_RETENTION_POLICY` | `str` | `"preserve"` | `books.conversion.retention_policy` |
| `MEDIA_CRON_BOOKS_ARCHIVE_DIR` | `str` | `None` | `books.conversion.archive_dir` |
| `MEDIA_CRON_BOOKS_CACHE_FILE` | `str` | `".media-cron-cache/book_cache.json"` | `books.cache.cache_file` |
| `MEDIA_CRON_BOOKS_CACHE_TTL` | `int` | `2592000` | `books.cache.ttl_seconds` |
