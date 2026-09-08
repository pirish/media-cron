import json
from pathlib import Path

import typer

# Import plugins to trigger registrations
import media_cron.plugins.input.directory  # noqa: F401
import media_cron.plugins.input.torrent  # noqa: F401
import media_cron.plugins.lookup.audio  # noqa: F401
import media_cron.plugins.lookup.book  # noqa: F401
import media_cron.plugins.lookup.video  # noqa: F401
import media_cron.plugins.output.cleaner  # noqa: F401
import media_cron.plugins.output.organizer  # noqa: F401
import media_cron.plugins.output.seed  # noqa: F401
import media_cron.torrent  # noqa: F401
from media_cron.config import MediaCronConfig
from media_cron.models import (
    EXIT_CONFIG_ERROR,
    EXIT_FATAL_ERROR,
    EXIT_SUCCESS,
    BatchSummary,
)
from media_cron.pipeline import Pipeline
from media_cron.torrent.base import TorrentClientRegistry
from media_cron.torrent.models import TorrentClientConfig

app = typer.Typer(
    name="media-cron",
    help="Pluggable media file organizer, cleaner, and torrent staging manager.",
    add_completion=False,
)


@app.command("version")
def version() -> None:
    """Show the media-cron version."""
    typer.echo("media-cron v0.1.0")


def render_text_summary(summary: BatchSummary) -> str:
    lines = [
        "=== Media-Cron Batch Summary ===",
        f"Batch ID: {summary.batch_id}",
        f"Started:  {summary.started_at}",
        f"Finished: {summary.completed_at}",
        f"Mode:     {'[DRY-RUN SIMULATION]' if summary.dry_run else '[LIVE EXECUTION]'}",
        f"Scanned:  {summary.total_scanned}",
        f"Organized: {summary.processed_count}",
        f"Upgraded: {summary.upgraded_count}",
        f"Junk/Sample Purged: {summary.junk_purged_count}",
        f"Skipped:  {summary.skipped_count}",
        f"Errors:   {summary.error_count}",
        f"Exit Code: {summary.exit_code}",
    ]
    if summary.torrent_summary:
        ts = summary.torrent_summary
        lines.extend(
            [
                "--- Torrent Client Telemetry ---",
                f"Client:             {ts.get('client')}",
                f"Discovered Torrents: {ts.get('discovered_torrents', 0)}",
                f"Ingested Torrents:   {ts.get('ingested_torrents', 0)}",
                f"Relocated Torrents:  {ts.get('relocated_torrents', 0)}",
                f"Tagged Torrents:     {ts.get('tagged_torrents', 0)}",
            ]
        )
    lines.append("--- Operations ---")
    for op in summary.operations:
        status_tag = f"[{op.status.value}]"
        dest = f" -> {op.plan.destination_path}" if op.plan.destination_path else ""
        lines.append(
            f"{status_tag} {op.plan.op_type.value}: {op.plan.source_path.name}{dest} ({op.plan.reason})"
        )
    if summary.errors:
        lines.append("--- Errors ---")
        for err in summary.errors:
            lines.append(f"ERROR: {err}")
    return "\n".join(lines)


@app.command("run")
@app.command("organize")
def run_command(
    source: Path | None = typer.Option(
        None, "--source", "--source-dir", "-s", help="Directory containing raw downloads"
    ),
    destination: Path | None = typer.Option(
        None, "--destination", "--destination-dir", "-d", help="Target media library root"
    ),
    staging: Path | None = typer.Option(
        None, "--staging", "--staging-dir", help="Staging directory for processing isolation"
    ),
    seed_dir: Path | None = typer.Option(
        None, "--seed-dir", help="Directory to relocate original files for seeding"
    ),
    mode: str | None = typer.Option(
        None, "--mode", "-m", help="Transfer mode: hardlink, move, copy"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", "-n", help="Simulate actions without disk writes"
    ),
    torrent_client: str | None = typer.Option(
        None, "--torrent-client", help="Enable torrent client ingestion (e.g. 'qbittorrent')"
    ),
    hybrid: bool = typer.Option(
        False,
        "--hybrid/--no-hybrid",
        help="Run both folder monitoring and torrent client ingestion",
    ),
    torrent_hash: str | None = typer.Option(
        None, "--torrent-hash", help="Target a specific completed torrent by info-hash"
    ),
    torrent_name: str | None = typer.Option(
        None, "--torrent-name", help="Target a specific completed torrent by release name"
    ),
    seeding_mode: str | None = typer.Option(
        None, "--seeding-mode", help="Seeding strategy: client_relocate, direct_filesystem, none"
    ),
    format: str = typer.Option("text", "--format", "-f", help="Output stream format: text or json"),
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Path to YAML configuration file"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose diagnostic output"),
) -> None:
    """Ingest, clean, sanitize, and organize media into destination library."""
    # 1. Load config
    cfg = MediaCronConfig.load(config_path=config)

    # 2. Apply CLI overrides
    if source:
        cfg.paths.source_dir = source
    if destination:
        cfg.paths.destination_dir = destination
    if staging:
        cfg.paths.staging_dir = staging
    if seed_dir:
        cfg.paths.seed_dir = seed_dir
    if mode:
        cfg.general.mode = mode
    if dry_run:
        cfg.general.dry_run = True
    if torrent_client:
        cfg.active_torrent_client = torrent_client
    if hybrid:
        cfg.hybrid_ingest = True

    if seeding_mode and cfg.active_torrent_client:
        if cfg.active_torrent_client not in cfg.torrent_clients:
            cfg.torrent_clients[cfg.active_torrent_client] = TorrentClientConfig(
                client_type=cfg.active_torrent_client
            )
        cfg.torrent_clients[cfg.active_torrent_client].seeding.mode = seeding_mode

    # 3. Validate paths
    if not cfg.paths.destination_dir:
        msg = "Error: --destination must be specified via CLI or config file."
        if format.lower() == "json":
            typer.echo(json.dumps({"exit_code": EXIT_CONFIG_ERROR, "errors": [msg]}))
        else:
            typer.echo(msg, err=True)
        raise typer.Exit(code=EXIT_CONFIG_ERROR)

    if not cfg.active_torrent_client and not cfg.paths.source_dir:
        msg = "Error: Either --source or --torrent-client must be specified."
        if format.lower() == "json":
            typer.echo(json.dumps({"exit_code": EXIT_CONFIG_ERROR, "errors": [msg]}))
        else:
            typer.echo(msg, err=True)
        raise typer.Exit(code=EXIT_CONFIG_ERROR)

    target_ident = torrent_hash or torrent_name

    # 4. Run pipeline
    pipeline = Pipeline(config=cfg, target_torrent_identifier=target_ident)
    summary = pipeline.run()

    # 5. Output
    if format.lower() == "json":
        typer.echo(json.dumps(summary.to_dict(), indent=2))
    else:
        typer.echo(render_text_summary(summary))

    raise typer.Exit(code=summary.exit_code)


@app.command("test-client")
def test_client(
    torrent_client: str | None = typer.Option(
        None,
        "--torrent-client",
        help="Client provider to test ('qbittorrent', 'transmission', 'deluge')",
    ),
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Path to YAML configuration file"
    ),
    format: str = typer.Option("text", "--format", "-f", help="Output stream format: text or json"),
) -> None:
    """Validates connectivity and authentication against the configured torrent client."""
    cfg = MediaCronConfig.load(config_path=config)
    client_name = torrent_client or cfg.active_torrent_client or "qbittorrent"

    client_cfg = cfg.torrent_clients.get(client_name) or TorrentClientConfig(
        client_type=client_name
    )

    try:
        client = TorrentClientRegistry.create_client(client_cfg)
        connected = client.test_connection()
    except Exception as e:
        if format.lower() == "json":
            typer.echo(
                json.dumps(
                    {
                        "status": "FAILED",
                        "client": client_name,
                        "error": str(e),
                        "exit_code": EXIT_FATAL_ERROR,
                    }
                )
            )
        else:
            typer.echo(f"[ERROR] Failed to initialize client '{client_name}': {e}", err=True)
        raise typer.Exit(code=EXIT_FATAL_ERROR) from e

    if connected:
        if format.lower() == "json":
            typer.echo(
                json.dumps(
                    {
                        "status": "SUCCESS",
                        "connected": True,
                        "client": client_name,
                        "exit_code": EXIT_SUCCESS,
                    }
                )
            )
        else:
            typer.echo(f"[SUCCESS] Connected to {client_name} Web API v2.")
        raise typer.Exit(code=EXIT_SUCCESS)
    else:
        if format.lower() == "json":
            typer.echo(
                json.dumps(
                    {
                        "status": "FAILED",
                        "connected": False,
                        "client": client_name,
                        "error": "Connection or authentication failed",
                        "exit_code": EXIT_FATAL_ERROR,
                    }
                )
            )
        else:
            typer.echo(
                f"[ERROR] Connection or authentication failed for {client_name}.",
                err=True,
            )
        raise typer.Exit(code=EXIT_FATAL_ERROR)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
