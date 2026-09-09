import json
from pathlib import Path

import typer

# Import plugins to trigger registrations
import media_cron.plugins.input.directory  # noqa: F401
import media_cron.plugins.input.torrent  # noqa: F401
import media_cron.plugins.lookup.audio  # noqa: F401
import media_cron.plugins.lookup.book  # noqa: F401
import media_cron.plugins.lookup.music  # noqa: F401
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
    if summary.audiobook_summary:
        asum = summary.audiobook_summary
        lines.extend(
            [
                "--- Audiobook Telemetry ---",
                f"Total Audiobooks:      {asum.get('total_audiobooks', 0)}",
                f"Identified External:   {asum.get('identified_external', 0)}",
                f"Identified Local Only: {asum.get('identified_local_only', 0)}",
                f"Cache Hits:            {asum.get('cache_hits', 0)}",
                f"Cache Misses:          {asum.get('cache_misses', 0)}",
                f"Average Confidence:    {asum.get('average_confidence', 0.0)}",
            ]
        )
    if summary.books_summary:
        bsum = summary.books_summary
        lines.extend(
            [
                "--- Books Telemetry ---",
                f"Total Books:           {bsum.get('total_books', 0)}",
                f"Identified External:   {bsum.get('identified_external', 0)}",
                f"Identified Local Only: {bsum.get('identified_local_only', 0)}",
                f"Cache Hits:            {bsum.get('cache_hits', 0)}",
                f"Cache Misses:          {bsum.get('cache_misses', 0)}",
                f"Average Confidence:    {bsum.get('average_confidence', 0.0)}",
            ]
        )
    if summary.music_summary:
        msum = summary.music_summary
        lines.extend(
            [
                "--- Music Telemetry ---",
                f"Total Tracks:       {msum.get('total_tracks', 0)}",
                f"Releases Bundled:   {msum.get('releases_bundled', 0)}",
                f"Spooled Releases:   {msum.get('spooled_releases', 0)}",
                f"Organized Tracks:   {msum.get('organized_tracks', 0)}",
                f"External Matches:   {msum.get('external_matches', 0)}",
                f"Average Confidence: {msum.get('average_confidence', 0.0)}",
                f"Post Commands Run:  {msum.get('post_commands_run', 0)}",
                f"Errors:             {msum.get('errors', 0)}",
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
@app.command("process")
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
    audiobook_lookup: bool | None = typer.Option(
        None,
        "--audiobook-lookup/--no-audiobook-lookup",
        help="Enable or disable external book metadata queries for audiobooks",
    ),
    audiobook_provider: str | None = typer.Option(
        None,
        "--audiobook-provider",
        help="Specific provider to force for audiobook lookups ('openlibrary', 'audnexus')",
    ),
    audiobook_confidence_threshold: float | None = typer.Option(
        None,
        "--audiobook-confidence-threshold",
        help="Custom confidence threshold [0.0, 1.0] required to override local author/title tags",
    ),
    audiobook_cache: bool | None = typer.Option(
        None,
        "--audiobook-cache/--no-audiobook-cache",
        help="Enable or disable response caching for audiobooks",
    ),
    books: bool | None = typer.Option(
        None,
        "--books/--no-books",
        help="Enable or disable digital book processing",
    ),
    book_lookup: bool | None = typer.Option(
        None,
        "--book-lookup/--no-book-lookup",
        help="Enable or disable external catalog identification for books",
    ),
    udc_lookup: bool | None = typer.Option(
        None,
        "--udc-lookup/--no-udc-lookup",
        help="Enable or disable Universal Decimal Classification lookup",
    ),
    convert_epub: bool | None = typer.Option(
        None,
        "--convert-epub/--no-convert-epub",
        help="Convert non-standard book formats to EPUB",
    ),
    retention: str | None = typer.Option(
        None,
        "--retention",
        help="Retention policy for original files after EPUB conversion: preserve, archive, replace",
    ),
    archive_dir: Path | None = typer.Option(
        None,
        "--archive-dir",
        help="Target archive directory when retention is 'archive'",
    ),
    music: bool | None = typer.Option(
        None,
        "--music/--no-music",
        help="Enable or disable music processing",
    ),
    music_mode: str | None = typer.Option(
        None,
        "--music-mode",
        help="Operational workflow mode: spool, direct, hybrid",
    ),
    music_spool_dir: Path | None = typer.Option(
        None,
        "--music-spool-dir",
        help="Drop/spool directory where releases are deposited for external managers like beets",
    ),
    music_post_command: str | None = typer.Option(
        None,
        "--music-post-command",
        help="Optional shell command hook executed upon successful release drop",
    ),
    music_lookup: bool | None = typer.Option(
        None,
        "--music-lookup/--no-music-lookup",
        help="Enable or disable online music catalog lookup",
    ),
    music_provider: str | None = typer.Option(
        None,
        "--music-provider",
        help="Primary online catalog provider: musicbrainz, discogs",
    ),
    discogs_token: str | None = typer.Option(
        None,
        "--discogs-token",
        help="Optional personal access token for Discogs API queries",
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

    # Audiobook CLI overrides
    if audiobook_lookup is not None:
        cfg.audiobook.enable_external_lookup = audiobook_lookup
    if audiobook_confidence_threshold is not None:
        cfg.audiobook.confidence_threshold = audiobook_confidence_threshold
    if audiobook_cache is not None:
        cfg.audiobook.cache.enabled = audiobook_cache
    if audiobook_provider:
        target_p = audiobook_provider.lower()
        if target_p in cfg.audiobook.providers:
            for pname, pcfg in cfg.audiobook.providers.items():
                if pname == target_p:
                    pcfg.enabled = True
                    pcfg.priority = 1
                else:
                    pcfg.enabled = False
        else:
            from media_cron.config import ExternalProviderConfig

            cfg.audiobook.providers = {
                target_p: ExternalProviderConfig(provider_name=target_p, enabled=True, priority=1)
            }

    # Book CLI overrides
    if books is not None:
        cfg.books.enabled = books
    if book_lookup is not None:
        cfg.books.enable_external_lookup = book_lookup
    if udc_lookup is not None:
        cfg.books.udc_lookup.enabled = udc_lookup
    if convert_epub is not None:
        cfg.books.conversion.enabled = convert_epub
    if retention:
        cfg.books.conversion.retention_policy = retention.lower()
    if archive_dir:
        cfg.books.conversion.archive_dir = archive_dir

    # Music CLI overrides
    if music is not None:
        cfg.music.enabled = music
    if music_mode is not None:
        cfg.music.workflow_mode = music_mode.lower()
    if music_spool_dir is not None:
        cfg.music.spool_dir = music_spool_dir
        if music_mode is None and cfg.music.workflow_mode == "direct":
            cfg.music.workflow_mode = "spool"
    if music_post_command is not None:
        cfg.music.post_ingest_command = music_post_command
    if music_lookup is not None:
        cfg.music.enable_external_lookup = music_lookup
    if music_provider is not None:
        cfg.music.primary_provider = music_provider.lower()
    if discogs_token is not None:
        cfg.music.discogs_token = discogs_token

    if seeding_mode and cfg.active_torrent_client:
        if cfg.active_torrent_client not in cfg.torrent_clients:
            cfg.torrent_clients[cfg.active_torrent_client] = TorrentClientConfig(
                client_type=cfg.active_torrent_client
            )
        cfg.torrent_clients[cfg.active_torrent_client].seeding.mode = seeding_mode

    # 3. Validate paths
    if not cfg.paths.destination_dir and not (cfg.music.enabled and cfg.music.spool_dir):
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


@app.command("test-book-lookup")
def test_book_lookup(
    title: str = typer.Argument(..., help="Book or work title to search for"),
    author: str | None = typer.Option(None, "--author", "-a", help="Author name to narrow query"),
    provider: str = typer.Option(
        "openlibrary",
        "--provider",
        "-p",
        help="Metadata provider to query ('openlibrary', 'audnexus')",
    ),
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Path to YAML configuration file"
    ),
    format: str = typer.Option("text", "--format", "-f", help="Output stream format: text or json"),
) -> None:
    """Diagnostic command to validate metadata provider connectivity and query parsing."""
    import time

    from media_cron.metadata.base import ProviderError, default_provider_registry
    from media_cron.metadata.cache import MetadataCache
    from media_cron.metadata.scorer import ConfidenceScorer

    cfg = MediaCronConfig.load(config_path=config)
    target_prov = provider.lower()
    prov_cfg = cfg.audiobook.providers.get(target_prov)
    if not prov_cfg:
        from media_cron.config import ExternalProviderConfig

        prov_cfg = ExternalProviderConfig(provider_name=target_prov)

    cache = (
        MetadataCache(cache_file=cfg.audiobook.cache.cache_file)
        if cfg.audiobook.cache.enabled
        else None
    )
    scorer = ConfidenceScorer()

    start_time = time.time()
    cached = False
    top_match = None
    matches_found = 0

    try:
        if cache:
            cached_match = cache.get(target_prov, title, author)
            if cached_match is not None:
                cached = True
                top_match = cached_match
                matches_found = 1

        if top_match is None:
            prov_cls = default_provider_registry.get(target_prov)
            try:
                inst = prov_cls(scorer=scorer)
            except TypeError:
                inst = prov_cls()
            results = inst.search(title=title, author=author, config=prov_cfg)
            matches_found = len(results)
            if results:
                top_match = results[0]
                if cache:
                    cache.put(
                        target_prov,
                        title,
                        author,
                        top_match,
                        ttl_seconds=cfg.audiobook.cache.ttl_seconds,
                    )

        latency_ms = round((time.time() - start_time) * 1000, 1)

        payload = {
            "query_title": title,
            "query_author": author,
            "provider": target_prov,
            "matches_found": matches_found,
            "top_match": (
                {
                    "title": top_match.title,
                    "author": top_match.author,
                    "year": top_match.year,
                    "narrator": top_match.narrator,
                    "series": top_match.series,
                    "work_id": top_match.work_id,
                    "confidence": top_match.confidence,
                }
                if top_match
                else None
            ),
            "cached": cached,
            "latency_ms": latency_ms,
        }

        if format.lower() == "json":
            typer.echo(json.dumps(payload, indent=2))
        else:
            lines = [
                "=== Book Lookup Diagnostic ===",
                f"Query Title:   {title}",
                f"Query Author:  {author or 'None'}",
                f"Provider:      {target_prov}",
                f"Matches Found: {matches_found}",
                f"Cached:        {cached}",
                f"Latency:       {latency_ms:.1f}ms",
            ]
            if top_match:
                lines.extend(
                    [
                        "Top Match:",
                        f"  Title:      {top_match.title}",
                        f"  Author:     {top_match.author}",
                        f"  Year:       {top_match.year}",
                        f"  Narrator:   {top_match.narrator}",
                        f"  Series:     {top_match.series}",
                        f"  Work ID:    {top_match.work_id}",
                        f"  Confidence: {top_match.confidence}",
                    ]
                )
            else:
                lines.append("No matches found.")
            typer.echo("\n".join(lines))
    except (ProviderError, KeyError, Exception) as e:
        if format.lower() == "json":
            typer.echo(json.dumps({"exit_code": 1, "error": str(e)}, indent=2))
        else:
            typer.echo(f"Error during lookup: {e}", err=True)
        raise typer.Exit(code=1) from e


@app.command("test-book-identify")
def test_book_identify(
    file_or_title: str = typer.Argument(..., help="Path to book file or book title query"),
    author: str | None = typer.Option(None, "--author", "-a", help="Author name to narrow query"),
    udc: bool = typer.Option(
        True, "--udc/--no-udc", help="Include Universal Decimal Classification lookup"
    ),
    format: str = typer.Option(
        "text", "--format", "-f", help="Output display format: table/text or json"
    ),
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Path to YAML configuration file"
    ),
) -> None:
    """Diagnostic command to test digital book identification and UDC classification."""
    from media_cron.metadata.book_identifier import BookIdentifier
    from media_cron.metadata.book_reader import BookMetadataReader
    from media_cron.metadata.models import BookMetadata
    from media_cron.metadata.udc import UDCResolver

    cfg = MediaCronConfig.load(config_path=config)
    cfg.books.udc_lookup.enabled = udc
    udc_resolver = UDCResolver() if udc else None
    identifier = BookIdentifier(config=cfg.books, udc_resolver=udc_resolver)

    path_candidate = Path(file_or_title)
    if path_candidate.exists() and path_candidate.is_file():
        local_meta = BookMetadataReader().read_metadata(path_candidate)
        if author:
            local_meta.author = author
        asset = identifier.identify(local_metadata=local_meta, path=path_candidate)
    else:
        local_meta = BookMetadata(title=file_or_title, author=author or "Unknown Author")
        asset = identifier.identify(local_metadata=local_meta)

    if not udc:
        asset.udc_classification = None

    if format.lower() == "json":
        payload = {
            "status": "success",
            "source_file": str(file_or_title),
            "identified": {
                "title": asset.title,
                "author": asset.author,
                "series": asset.canonical_metadata.series_name,
                "volume": asset.canonical_metadata.volume_number,
                "year": asset.canonical_metadata.publication_year,
                "isbn": asset.canonical_metadata.isbn,
                "provider": asset.match_source,
                "confidence": round(asset.confidence, 2),
            },
            "udc": (
                {
                    "notation": asset.udc_classification.notation,
                    "description": asset.udc_classification.description,
                    "confidence": asset.udc_classification.confidence,
                    "source": asset.udc_classification.source,
                }
                if asset.udc_classification
                else None
            ),
        }
        typer.echo(json.dumps(payload, indent=2))
    else:
        lines = [
            "=== Book Identification Diagnostic ===",
            f"Source:     {file_or_title}",
            f"Title:      {asset.title}",
            f"Author:     {asset.author}",
            f"Year:       {asset.canonical_metadata.publication_year or 'Unknown'}",
            f"ISBN:       {asset.canonical_metadata.isbn or 'None'}",
            f"Provider:   {asset.match_source}",
            f"Confidence: {asset.confidence:.2f}",
        ]
        if asset.udc_classification:
            lines.extend(
                [
                    "UDC Classification:",
                    f"  Notation:    {asset.udc_classification.notation}",
                    f"  Description: {asset.udc_classification.description}",
                    f"  Source:      {asset.udc_classification.source}",
                ]
            )
        typer.echo("\n".join(lines))
    raise typer.Exit(code=EXIT_SUCCESS)


@app.command("test-book-convert")
def test_book_convert(
    source_file: Path = typer.Argument(..., help="Path to source book file to convert"),
    output_dir: Path | None = typer.Option(
        None, "--output-dir", "-o", help="Where to place the converted test EPUB"
    ),
    engine: str = typer.Option(
        "auto", "--engine", "-e", help="Preferred conversion engine: auto, calibre, python"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", "-n", help="Check conversion feasibility without creating files"
    ),
    format: str = typer.Option("text", "--format", "-f", help="Output stream format: text or json"),
) -> None:
    """Diagnostic command to convert a single book file to standard EPUB."""
    from media_cron.metadata.book_reader import BookMetadataReader
    from media_cron.metadata.converter import (
        ConversionFailedError,
        ConverterUnavailableError,
        default_converter_registry,
    )
    from media_cron.metadata.models import BookFormat

    if not source_file.exists():
        msg = f"Source file does not exist: {source_file}"
        if format.lower() == "json":
            typer.echo(json.dumps({"status": "error", "error": msg, "exit_code": EXIT_FATAL_ERROR}))
        else:
            typer.echo(f"Error: {msg}", err=True)
        raise typer.Exit(code=EXIT_FATAL_ERROR)

    fmt = BookFormat.from_path(source_file)
    engine_map = {
        "auto": "calibre",
        "calibre": "calibre",
        "python": "python_fallback",
        "python_fallback": "python_fallback",
    }
    pref_engine = engine_map.get(engine.lower(), "calibre")

    try:
        converter = default_converter_registry.get_preferred_converter(
            fmt, preferred_engine=pref_engine
        )
    except ConverterUnavailableError as e:
        if format.lower() == "json":
            typer.echo(json.dumps({"status": "error", "error": str(e), "exit_code": 2}))
        else:
            typer.echo(f"Dependency Error: {e}", err=True)
        raise typer.Exit(code=2) from e

    out_folder = output_dir or source_file.parent
    target_epub = out_folder / f"{source_file.stem}.epub"

    if dry_run:
        payload = {
            "status": "simulated",
            "source_file": str(source_file),
            "target_file": str(target_epub),
            "engine": converter.engine_name,
            "dry_run": True,
        }
        if format.lower() == "json":
            typer.echo(json.dumps(payload, indent=2))
        else:
            typer.echo(
                f"[DRY-RUN] Would convert {source_file.name} to {target_epub} using {converter.engine_name}"
            )
        raise typer.Exit(code=EXIT_SUCCESS)

    out_folder.mkdir(parents=True, exist_ok=True)
    metadata = BookMetadataReader().read_metadata(source_file)
    try:
        converter.convert(source_path=source_file, target_path=target_epub, metadata=metadata)
    except ConversionFailedError as e:
        if format.lower() == "json":
            typer.echo(json.dumps({"status": "error", "error": str(e), "exit_code": 1}))
        else:
            typer.echo(f"Conversion failed: {e}", err=True)
        raise typer.Exit(code=1) from e

    payload = {
        "status": "success",
        "source_file": str(source_file),
        "target_file": str(target_epub),
        "engine": converter.engine_name,
        "output_size_bytes": target_epub.stat().st_size,
    }
    if format.lower() == "json":
        typer.echo(json.dumps(payload, indent=2))
    else:
        typer.echo(
            f"Successfully converted {source_file.name} -> {target_epub} ({converter.engine_name})"
        )
    raise typer.Exit(code=EXIT_SUCCESS)


@app.command("test-music-identify")
def test_music_identify(
    path: Path = typer.Argument(..., help="Path to an audio track or directory release bundle"),
    lookup: bool = typer.Option(
        False, "--lookup/--no-lookup", help="Enable/disable external catalog query"
    ),
    format: str = typer.Option(
        "text", "--format", "-f", help="Output display format: table/text or json"
    ),
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Path to YAML configuration file"
    ),
) -> None:
    """Diagnostic command to extract metadata and test external catalog identification."""
    from media_cron.metadata.music_bundler import MusicReleaseBundleAggregator
    from media_cron.metadata.music_identifier import MusicIdentifier
    from media_cron.metadata.music_reader import MusicMetadataReader

    cfg = MediaCronConfig.load(config_path=config)
    if lookup:
        cfg.music.enable_external_lookup = True

    if not path.exists():
        msg = f"Path '{path}' not found."
        if format.lower() == "json":
            typer.echo(json.dumps({"status": "error", "error": msg}))
        else:
            typer.echo(msg, err=True)
        raise typer.Exit(code=1)

    reader = MusicMetadataReader()
    bundler = MusicReleaseBundleAggregator()

    track = None
    bundle = None

    if path.is_file():
        track = reader.read(path)
        bundle = bundler.get_bundle(path)
    else:
        bundles = bundler.aggregate(path)
        bundle = bundles[0] if bundles else None
        track = bundle.tracks[0] if bundle and bundle.tracks else None

    catalog_match = None
    if lookup:
        identifier = MusicIdentifier(config=cfg.music)
        query_artist = (
            (track.artist if track and track.artist != "Unknown Artist" else None)
            or (bundle.album_artist if bundle and bundle.album_artist != "Unknown Artist" else None)
            or ""
        )
        query_album = (
            (track.album if track and track.album != "Unknown Album" else None)
            or (bundle.album_title if bundle and bundle.album_title != "Unknown Album" else None)
            or ""
        )
        track_count = len(bundle.tracks) if bundle and bundle.tracks else None
        year = (track.year if track else None) or (bundle.year if bundle else None)

        if query_artist or query_album:
            catalog_match = identifier.identify(
                artist=query_artist,
                album=query_album,
                track_count=track_count,
                year=year,
            )

    if format.lower() == "json":
        payload = {
            "status": "success",
            "path": str(path),
            "track": (
                {
                    "title": track.title,
                    "artist": track.artist,
                    "album": track.album,
                    "album_artist": track.album_artist,
                    "track_number": track.track_number,
                    "disc_number": track.disc_number,
                    "year": track.year,
                    "genre": track.genre,
                    "format": track.format.value
                    if hasattr(track.format, "value")
                    else str(track.format),
                    "bitrate_kbps": track.bitrate_kbps,
                }
                if track
                else None
            ),
            "release_bundle": (
                {
                    "album_title": bundle.album_title,
                    "album_artist": bundle.album_artist,
                    "year": bundle.year,
                    "total_tracks": len(bundle.tracks),
                    "total_discs": bundle.total_discs,
                    "companion_files": [c.path.name for c in bundle.companion_assets],
                }
                if bundle
                else None
            ),
            "catalog_match": (
                {
                    "title": catalog_match.title,
                    "artist": catalog_match.artist,
                    "release_id": catalog_match.release_id,
                    "provider": catalog_match.provider,
                    "confidence": round(catalog_match.confidence, 2),
                    "year": catalog_match.year,
                    "track_count": catalog_match.track_count,
                }
                if catalog_match
                else None
            ),
        }
        typer.echo(json.dumps(payload, indent=2))
    else:
        lines = [
            "=== Music Identification Diagnostic ===",
            f"Path:           {path}",
        ]
        if track:
            lines.extend(
                [
                    f"Title:          {track.title}",
                    f"Artist:         {track.artist}",
                    f"Album:          {track.album}",
                    f"Year:           {track.year or 'Unknown'}",
                    f"Format:         {track.format.value if hasattr(track.format, 'value') else track.format}",
                ]
            )
        if bundle:
            lines.extend(
                [
                    "Release Bundle:",
                    f"  Album:        {bundle.album_title}",
                    f"  Artist:       {bundle.album_artist}",
                    f"  Tracks:       {len(bundle.tracks)}",
                    f"  Discs:        {bundle.total_discs}",
                    f"  Companions:   {', '.join([c.path.name for c in bundle.companion_assets]) or 'None'}",
                ]
            )
        if catalog_match:
            lines.extend(
                [
                    "Catalog Match:",
                    f"  Title:        {catalog_match.title}",
                    f"  Artist:       {catalog_match.artist}",
                    f"  Release ID:   {catalog_match.release_id}",
                    f"  Provider:     {catalog_match.provider}",
                    f"  Confidence:   {catalog_match.confidence:.2f}",
                ]
            )
        typer.echo("\n".join(lines))
    raise typer.Exit(code=EXIT_SUCCESS)


@app.command("test-music-spool")
def test_music_spool(
    source_path: Path = typer.Argument(..., help="Directory containing the release to spool"),
    spool_dir: Path = typer.Option(..., "--spool-dir", help="Target drop folder destination"),
    post_command: str | None = typer.Option(
        None, "--post-command", help="Shell command template to execute"
    ),
    dry_run: bool = typer.Option(
        True, "--dry-run/--no-dry-run", help="Simulate deposition without copying/moving files"
    ),
    format: str = typer.Option("text", "--format", "-f", help="Output format: text or json"),
) -> None:
    """Diagnostic command to simulate or perform atomic drop-folder release deposition."""
    from media_cron.metadata.music_bundler import MusicReleaseBundleAggregator
    from media_cron.metadata.music_spooler import MusicSpoolEngine

    if not source_path.exists():
        msg = f"Source directory '{source_path}' does not exist."
        if format.lower() == "json":
            typer.echo(json.dumps({"status": "error", "error": msg}))
        else:
            typer.echo(msg, err=True)
        raise typer.Exit(code=1)

    bundler = MusicReleaseBundleAggregator()
    bundle = bundler.get_bundle(source_path)
    if not bundle:
        bundles = bundler.aggregate(source_path)
        bundle = bundles[0] if bundles else None

    if not bundle:
        msg = f"No music release bundle found in '{source_path}'."
        if format.lower() == "json":
            typer.echo(json.dumps({"status": "error", "error": msg}))
        else:
            typer.echo(msg, err=True)
        raise typer.Exit(code=1)

    spooler = MusicSpoolEngine()
    target_release_path = spool_dir / bundle.root_path.name
    files_transferred = [str(t.path.relative_to(bundle.root_path)) for t in bundle.tracks] + [
        str(c.path.relative_to(bundle.root_path)) for c in bundle.companion_assets
    ]

    post_cmd_rendered = (
        post_command.replace("{release_path}", str(target_release_path)) if post_command else None
    )

    if dry_run:
        status = "success"
        post_cmd_exit = 0 if post_command else None
    else:
        spool_res = spooler.spool_release(
            bundle=bundle,
            spool_dir=spool_dir,
            post_command=post_command,
            dry_run=False,
        )
        status = "success" if spool_res.success else "failed"
        post_cmd_exit = spool_res.post_command_exit_code

    if format.lower() == "json":
        payload = {
            "status": status,
            "dry_run": dry_run,
            "source_dir": str(source_path),
            "spool_dir": str(spool_dir),
            "target_release_path": str(target_release_path),
            "files_transferred": files_transferred,
            "post_command": post_cmd_rendered,
            "post_command_exit_code": post_cmd_exit,
        }
        typer.echo(json.dumps(payload, indent=2))
    else:
        lines = [
            "=== Music Spool Diagnostic ===",
            f"Status:         {status}",
            f"Mode:           {'[DRY-RUN SIMULATION]' if dry_run else '[LIVE EXECUTION]'}",
            f"Source Dir:     {source_path}",
            f"Spool Dir:      {spool_dir}",
            f"Target Release: {target_release_path}",
            f"Files ({len(files_transferred)}):",
        ]
        for f in files_transferred:
            lines.append(f"  {f}")
        if post_cmd_rendered:
            lines.extend(
                [
                    f"Post Command:   {post_cmd_rendered}",
                    f"Exit Code:      {post_cmd_exit if post_cmd_exit is not None else 'N/A'}",
                ]
            )
        typer.echo("\n".join(lines))
    raise typer.Exit(code=EXIT_SUCCESS if status == "success" else 1)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
