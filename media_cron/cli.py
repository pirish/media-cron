import json
from pathlib import Path

import typer

# Import plugins to trigger registrations
import media_cron.plugins.input.directory  # noqa: F401
import media_cron.plugins.lookup.audio  # noqa: F401
import media_cron.plugins.lookup.book  # noqa: F401
import media_cron.plugins.lookup.video  # noqa: F401
import media_cron.plugins.output.cleaner  # noqa: F401
import media_cron.plugins.output.organizer  # noqa: F401
import media_cron.plugins.output.seed  # noqa: F401
from media_cron.config import MediaCronConfig
from media_cron.models import (
    EXIT_CONFIG_ERROR,
    BatchSummary,
)
from media_cron.pipeline import Pipeline

app = typer.Typer(
    name="media-cron",
    help="Pluggable media file organizer, cleaner, and staging manager.",
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
        "--- Operations ---",
    ]
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


@app.command("organize")
def organize(
    source: Path | None = typer.Option(
        None, "--source", "-s", help="Directory containing raw downloads"
    ),
    destination: Path | None = typer.Option(
        None, "--destination", "-d", help="Target media library root"
    ),
    staging: Path | None = typer.Option(
        None, "--staging", help="Staging directory for processing isolation"
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

    # 3. Validate paths
    if not cfg.paths.source_dir or not cfg.paths.destination_dir:
        msg = "Error: Both --source and --destination must be specified via CLI or config file."
        if format.lower() == "json":
            typer.echo(json.dumps({"exit_code": EXIT_CONFIG_ERROR, "errors": [msg]}))
        else:
            typer.echo(msg, err=True)
        raise typer.Exit(code=EXIT_CONFIG_ERROR)

    # 4. Run pipeline
    pipeline = Pipeline(config=cfg)
    summary = pipeline.run()

    # 5. Output
    if format.lower() == "json":
        typer.echo(json.dumps(summary.to_dict(), indent=2))
    else:
        typer.echo(render_text_summary(summary))

    raise typer.Exit(code=summary.exit_code)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
