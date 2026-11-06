# Contract: Configuration, Environment Variables, and CLI Schema

**Feature**: `012-native-file-transfers`
**Modules**: `media_cron.config`, `media_cron.routing.models`, `media_cron.cli`

---

## 1. YAML Configuration Schema (`config.yaml`)

### Global Transfer Configuration
```yaml
transfer:
  strategy: native          # Options: "native" (default), "custom", "builtin"
  copy_command: null        # Optional custom copy template, e.g., "rsync -a {src} {dst}"
  move_command: null        # Optional custom move template, e.g., "rsync -a --remove-source-files {src} {dst}"
  fallback_enabled: true    # Default: true (fall back to Python builtin on non-ENOSPC tool failure)
  timeout_seconds: 3600.0   # Default: 3600.0 (1 hour max per external transfer invocation)
```

### Per-Destination Route Override (`routes.<media_type>.destination.transfer`)
```yaml
routes:
  movie:
    enabled: true
    destination:
      path: /mnt/nas/movies
      mode: copy
      transfer:
        strategy: custom
        copy_command: "rsync -a --inplace {src} {dst}"
        fallback_enabled: true
        timeout_seconds: 7200.0
```
- Any field omitted under `routes.<media_type>.destination.transfer` inherits from the global `transfer` configuration.

---

## 2. Environment Variable Overrides

Environment variables override the global `transfer:` block in `config.yaml`:

| Environment Variable | Type | Maps To | Example |
|----------------------|------|---------|---------|
| `MEDIA_CRON_TRANSFER_STRATEGY` | `str` | `transfer.strategy` | `native`, `custom`, `builtin` |
| `MEDIA_CRON_TRANSFER_COPY_COMMAND` | `str` | `transfer.copy_command` | `rsync -a {src} {dst}` |
| `MEDIA_CRON_TRANSFER_MOVE_COMMAND` | `str` | `transfer.move_command` | `rsync -a --remove-source-files {src} {dst}` |
| `MEDIA_CRON_TRANSFER_FALLBACK_ENABLED` | `bool` | `transfer.fallback_enabled` | `true` / `false` / `1` / `0` |
| `MEDIA_CRON_TRANSFER_TIMEOUT_SECONDS` | `float` | `transfer.timeout_seconds` | `1800` |

---

## 3. CLI Flags (`media-cron`)

CLI flags take highest precedence over global config and environment variables:

| CLI Flag | Type | Description |
|----------|------|-------------|
| `--transfer-strategy [native\|custom\|builtin]` | Choice | Override global file transfer strategy (`native`, `custom`, or `builtin`). |
| `--copy-cmd TEXT` | String | Custom command template for file/directory copy operations (automatically sets strategy to `custom` if `--transfer-strategy` is not explicitly provided). |
| `--move-cmd TEXT` | String | Custom command template for file/directory move operations (automatically sets strategy to `custom` if `--transfer-strategy` is not explicitly provided). |
| `--no-transfer-fallback` | Flag | Disable automatic fallback to built-in Python file streaming when external utilities fail. |
| `--transfer-timeout FLOAT` | Float | Maximum timeout in seconds for external transfer commands. |

---

## 4. Telemetry & Batch Summary Output Schema

### Structured Log Record Fields (Per Transfer)
Each completed transfer emits an `INFO` log containing:
- `action`: `"copy"` or `"move"`
- `strategy`: `"native"`, `"custom"`, or `"builtin"`
- `fallback_used`: `true` or `false`
- `bytes_transferred`: integer byte count
- `duration_ms`: float elapsed milliseconds
- `throughput_mbps`: float MB/s

### `BatchSummary` JSON Output (`--json-logs` / summary output)
`BatchSummary` includes `transfer_summary`:
```json
{
  "transfer_summary": {
    "native_count": 4,
    "custom_count": 0,
    "builtin_count": 1,
    "fallback_count": 1,
    "total_bytes_transferred": 4294967296,
    "total_duration_ms": 2150.4
  }
}
```
