# Contract: Configuration Schema & Environment Mappings

**Branch**: `002-torrent-client-integration` | **Date**: 2026-09-07 | **Spec**: [spec.md](../spec.md)

## YAML Configuration Specification

```yaml
# media-cron.yml configuration extensions for Torrent Client Integration

staging_dir: /var/lib/media-cron/staging
destination_dir: /mnt/media/library
seed_dir: /mnt/media/seeding

# Primary active torrent client (empty or null to disable client ingestion)
active_torrent_client: qbittorrent

# Hybrid execution: scan both source_dir and active_torrent_client
hybrid_ingest: false

torrent_clients:
  qbittorrent:
    client_type: qbittorrent
    host: localhost
    port: 8080
    username: admin
    password: adminadmin
    use_ssl: false
    timeout: 10.0

    # Path mappings between client container/host paths and media-cron local mounts
    path_mappings:
      - remote_prefix: /downloads/completed
        local_prefix: /mnt/media/downloads/completed

    # Ingestion eligibility filters
    filters:
      categories:
        - movies
        - tv
        - music
      tags: []
      exclude_tags:
        - media-cron-processed
      exclude_categories:
        - media-cron-done
      min_progress: 1.0

    # Seeding policy post-organization
    seeding:
      mode: client_relocate           # client_relocate | direct_filesystem | none
      target_location: seed_dir       # seed_dir | destination_dir
      completion_tag: media-cron-processed
      completion_category: media-cron-done
      pause_after_process: false

  # Optional future client plugin configurations
  transmission:
    client_type: transmission
    host: localhost
    port: 9091
    username: null
    password: null
    use_ssl: false
    timeout: 10.0
    path_mappings: []
    filters:
      categories: []
      tags: []
      exclude_tags:
        - media-cron-processed
      exclude_categories: []
      min_progress: 1.0
    seeding:
      mode: client_relocate
      target_location: seed_dir
      completion_tag: media-cron-processed
      completion_category: media-cron-done
      pause_after_process: false
```

---

## Environment Variable Mappings

In compliance with Constitution Principle V, all settings can be declared or overridden via environment variables:

| Environment Variable | YAML Path Equivalent | Default |
|---|---|---|
| `MEDIA_CRON_ACTIVE_TORRENT_CLIENT` | `active_torrent_client` | `None` |
| `MEDIA_CRON_HYBRID_INGEST` | `hybrid_ingest` | `false` |
| `MEDIA_CRON_QBITTORRENT_HOST` | `torrent_clients.qbittorrent.host` | `localhost` |
| `MEDIA_CRON_QBITTORRENT_PORT` | `torrent_clients.qbittorrent.port` | `8080` |
| `MEDIA_CRON_QBITTORRENT_USERNAME` | `torrent_clients.qbittorrent.username` | `None` |
| `MEDIA_CRON_QBITTORRENT_PASSWORD` | `torrent_clients.qbittorrent.password` | `None` |
| `MEDIA_CRON_SEEDING_MODE` | `torrent_clients.qbittorrent.seeding.mode` | `client_relocate` |
| `MEDIA_CRON_COMPLETION_TAG` | `torrent_clients.qbittorrent.seeding.completion_tag` | `media-cron-processed` |
| `MEDIA_CRON_COMPLETION_CATEGORY` | `torrent_clients.qbittorrent.seeding.completion_category` | `media-cron-done` |
