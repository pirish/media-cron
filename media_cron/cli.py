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
    if summary.video_summary:
        vsum = summary.video_summary
        lines.extend(
            [
                "--- Video Telemetry ---",
                f"Total Videos:          {vsum.get('total_videos', 0)}",
                f"Spooled Releases:      {vsum.get('spooled_releases', 0)}",
                f"Spool Skipped:         {vsum.get('spool_skipped_count', 0)}",
                f"Organized Movies:      {vsum.get('organized_movies', 0)}",
                f"Organized Episodes:    {vsum.get('organized_episodes', 0)}",
                f"Rescan Notifications:  {vsum.get('rescan_notifications_sent', 0)}",
                f"Rescan Errors:         {vsum.get('rescan_errors', 0)}",
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
    video: bool | None = typer.Option(
        None,
        "--video/--no-video",
        help="Enable or disable video processing",
    ),
    video_mode: str | None = typer.Option(
        None,
        "--video-mode",
        help="Operational workflow mode: spool, direct, hybrid",
    ),
    video_spool_dir: Path | None = typer.Option(
        None,
        "--video-spool-dir",
        help="Drop/spool directory where releases are deposited for external managers like Sonarr/Radarr",
    ),
    video_post_command: str | None = typer.Option(
        None,
        "--video-post-command",
        help="Optional shell command hook executed upon successful release drop",
    ),
    media_server: bool | None = typer.Option(
        None,
        "--media-server/--no-media-server",
        help="Enable/disable media server library rescan notification",
    ),
    media_server_provider: str | None = typer.Option(
        None,
        "--media-server-provider",
        help="Target media server provider: jellyfin, emby, plex",
    ),
    media_server_url: str | None = typer.Option(
        None,
        "--media-server-url",
        help="Base URL of media server",
    ),
    media_server_token: str | None = typer.Option(
        None,
        "--media-server-token",
        help="API token or authentication key for the media server",
    ),
    media_server_library_id: str | None = typer.Option(
        None,
        "--media-server-library-id",
        help="Optional specific library/section ID to refresh",
    ),
    media_server_max_retries: int | None = typer.Option(
        None,
        "--media-server-max-retries",
        help="Max retry attempts for rescan notifications",
    ),
    review_dir: Path | None = typer.Option(
        None,
        "--review-dir",
        help="Directory to stage unrecognized media for manual review",
    ),
    review_max_age_days: int | None = typer.Option(
        None,
        "--review-max-age-days",
        help="Retention limit in days for items in review directory (0 = disabled)",
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

    # Video CLI overrides
    if video is not None:
        cfg.video.enabled = video
    if video_mode is not None:
        cfg.video.workflow_mode = video_mode.lower()
        cfg.video.enabled = True
    if video_spool_dir is not None:
        cfg.video.spool_dir = video_spool_dir
        cfg.video.enabled = True
        if video_mode is None and cfg.video.workflow_mode == "direct":
            cfg.video.workflow_mode = "spool"
    if video_post_command is not None:
        cfg.video.post_ingest_command = video_post_command
    if media_server is not None:
        cfg.video.media_server.enabled = media_server
        if media_server:
            cfg.video.enabled = True
    if media_server_provider is not None:
        cfg.video.media_server.provider = media_server_provider.lower()
    if media_server_url is not None:
        cfg.video.media_server.url = media_server_url
    if media_server_token is not None:
        cfg.video.media_server.token = media_server_token
    if media_server_library_id is not None:
        cfg.video.media_server.library_id = media_server_library_id
    if media_server_max_retries is not None:
        cfg.video.media_server.max_retries = media_server_max_retries

    # Review CLI overrides
    if review_dir is not None:
        cfg.paths.review_dir = review_dir
    if review_max_age_days is not None:
        cfg.review.max_age_days = review_max_age_days

    if seeding_mode and cfg.active_torrent_client:
        if cfg.active_torrent_client not in cfg.torrent_clients:
            cfg.torrent_clients[cfg.active_torrent_client] = TorrentClientConfig(
                client_type=cfg.active_torrent_client
            )
        cfg.torrent_clients[cfg.active_torrent_client].seeding.mode = seeding_mode

    # 3. Validate paths
    if (
        not cfg.paths.destination_dir
        and not (cfg.music.enabled and cfg.music.spool_dir)
        and not (cfg.video.enabled and cfg.video.spool_dir)
    ):
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


@app.command("test-video-identify")
def test_video_identify(
    path: Path = typer.Argument(..., help="Path to a video file or directory release bundle"),
    format: str = typer.Option(
        "text", "--format", "-f", help="Output display format: text or json"
    ),
) -> None:
    """Diagnostic command to inspect video files, extract metadata, resolution, quality, and companion assets."""
    if not path.exists():
        msg = f"Path '{path}' not found."
        if format.lower() == "json":
            typer.echo(json.dumps({"status": "error", "error": msg}))
        else:
            typer.echo(msg, err=True)
        raise typer.Exit(code=1)

    from media_cron.metadata.video_bundler import VideoReleaseBundleAggregator
    from media_cron.models import DiscoveredItem
    from media_cron.plugins.lookup.video import SceneVideoLookup

    bundler = VideoReleaseBundleAggregator()
    lookup = SceneVideoLookup()

    track_dict = None
    bundle_dict = None

    if path.is_file():
        stat = path.stat()
        item = DiscoveredItem(
            source_path=path,
            file_size=stat.st_size,
            modified_time=stat.st_mtime,
            is_archive=False,
            is_directory=False,
        )
        asset = lookup.enrich(item)
        track_dict = {
            "title": asset.clean_title,
            "show_title": asset.series_title,
            "season_number": asset.season_number,
            "episode_number": asset.episode_number,
            "year": asset.year,
            "resolution": getattr(asset, "resolution", None),
            "source_quality": getattr(asset, "quality", None),
            "format": path.suffix.lstrip(".").lower(),
            "is_sample": False,
        }
        bundle = bundler.get_bundle(path)
    else:
        bundles = bundler.aggregate(path)
        bundle = bundles[0] if bundles else None
        if bundle and bundle.primary_videos:
            primary = bundle.primary_videos[0]
            track_dict = {
                "title": primary.title,
                "show_title": primary.show_title,
                "season_number": primary.season_number,
                "episode_number": primary.episode_number,
                "year": primary.year,
                "resolution": primary.resolution,
                "source_quality": primary.source_quality,
                "format": primary.format.value
                if hasattr(primary.format, "value")
                else str(primary.format),
                "is_sample": primary.is_sample,
            }

    if bundle:
        bundle_dict = {
            "release_title": bundle.release_title,
            "is_series": bundle.is_series,
            "show_title": bundle.show_title,
            "season_number": bundle.season_number,
            "total_videos": len(bundle.primary_videos),
            "companion_files": [c.path.name for c in bundle.companion_assets],
        }

    if format.lower() == "json":
        payload = {
            "status": "success",
            "path": str(path),
            "track": track_dict,
            "release_bundle": bundle_dict,
        }
        typer.echo(json.dumps(payload, indent=2))
    else:
        lines = [
            "=== Video Identification Diagnostic ===",
            f"Path:            {path}",
        ]
        if track_dict:
            lines.extend(
                [
                    f"Title:           {track_dict.get('title')}",
                    f"Show:            {track_dict.get('show_title') or 'N/A'}",
                    f"Season/Episode:  S{track_dict.get('season_number') or 0:02d}E{track_dict.get('episode_number') or 0:02d}"
                    if track_dict.get("season_number") is not None
                    else "N/A",
                    f"Year:            {track_dict.get('year') or 'N/A'}",
                    f"Resolution:      {track_dict.get('resolution') or 'N/A'}",
                    f"Quality:         {track_dict.get('source_quality') or 'N/A'}",
                    f"Format:          {track_dict.get('format')}",
                ]
            )
        if bundle_dict:
            lines.extend(
                [
                    f"Release Bundle:  {bundle_dict.get('release_title')}",
                    f"Total Videos:    {bundle_dict.get('total_videos')}",
                    f"Companions:      {', '.join(bundle_dict.get('companion_files', [])) or 'None'}",
                ]
            )
        typer.echo("\n".join(lines))
    raise typer.Exit(code=EXIT_SUCCESS)


@app.command("test-video-spool")
def test_video_spool(
    source_path: Path = typer.Argument(..., help="Directory containing the video release to spool"),
    spool_dir: Path = typer.Option(..., "--spool-dir", help="Target drop folder destination"),
    post_command: str | None = typer.Option(
        None, "--post-command", help="Shell command template to execute"
    ),
    dry_run: bool = typer.Option(
        True, "--dry-run/--no-dry-run", help="Simulate deposition without copying/moving files"
    ),
    format: str = typer.Option("text", "--format", "-f", help="Output format: text or json"),
) -> None:
    """Diagnostic command to simulate or perform atomic drop-folder video release deposition."""
    from media_cron.metadata.video_bundler import VideoReleaseBundleAggregator
    from media_cron.metadata.video_spooler import VideoSpoolEngine

    if not source_path.exists():
        msg = f"Source directory '{source_path}' does not exist."
        if format.lower() == "json":
            typer.echo(json.dumps({"status": "error", "error": msg}))
        else:
            typer.echo(msg, err=True)
        raise typer.Exit(code=1)

    bundler = VideoReleaseBundleAggregator()
    bundle = bundler.get_bundle(source_path)
    if not bundle:
        bundles = bundler.aggregate(source_path)
        bundle = bundles[0] if bundles else None

    if not bundle:
        msg = f"No video release bundle found in '{source_path}'."
        if format.lower() == "json":
            typer.echo(json.dumps({"status": "error", "error": msg}))
        else:
            typer.echo(msg, err=True)
        raise typer.Exit(code=1)

    spooler = VideoSpoolEngine()
    target_release_path = spool_dir / bundle.root_path.name
    files_transferred = [
        str(v.path.relative_to(bundle.root_path)) for v in bundle.primary_videos
    ] + [str(c.path.relative_to(bundle.root_path)) for c in bundle.companion_assets]

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
            "=== Video Spool Diagnostic ===",
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


@app.command("test-media-server-notify")
def test_media_server_notify(
    provider: str = typer.Option(
        "jellyfin", "--provider", help="Media server provider: jellyfin, emby, plex"
    ),
    url: str = typer.Option(..., "--url", help="Media server base URL"),
    token: str | None = typer.Option(None, "--token", help="API token or authentication key"),
    library_id: str | None = typer.Option(
        None, "--library-id", help="Optional specific library ID"
    ),
    dry_run: bool = typer.Option(
        True, "--dry-run/--no-dry-run", help="Simulate request without invoking server endpoint"
    ),
    format: str = typer.Option("text", "--format", "-f", help="Output format: text or json"),
) -> None:
    """Diagnostic command to test connectivity and authenticated library rescan on a media server."""
    from media_cron.metadata.media_servers import get_media_server_client
    from media_cron.metadata.models import MediaServerConfig

    cfg = MediaServerConfig(
        enabled=True,
        provider=provider,
        url=url,
        token=token or "",
        library_id=library_id,
        timeout_seconds=5.0,
        max_retries=0,
    )

    try:
        client = get_media_server_client(provider)
        res = client.trigger_rescan(
            config=cfg,
            library_id=library_id,
            dry_run=dry_run,
        )
    except Exception as e:
        if format.lower() == "json":
            typer.echo(json.dumps({"status": "error", "error": str(e)}))
        else:
            typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1) from e

    status = "success" if res.success else "failed"

    if format.lower() == "json":
        payload = {
            "status": status,
            "server_type": res.server_type,
            "endpoint": res.endpoint,
            "status_code": res.status_code,
            "duration_seconds": round(res.duration_seconds, 2),
            "dry_run": dry_run,
        }
        if res.error:
            payload["error"] = res.error
        typer.echo(json.dumps(payload, indent=2))
    else:
        lines = [
            "=== Media Server Notification Diagnostic ===",
            f"Status:         {status}",
            f"Server Type:    {res.server_type}",
            f"Endpoint:       {res.endpoint}",
            f"Status Code:    {res.status_code if res.status_code is not None else 'N/A'}",
            f"Duration:       {res.duration_seconds:.2f}s",
            f"Mode:           {'[DRY-RUN SIMULATION]' if dry_run else '[LIVE EXECUTION]'}",
        ]
        if res.error:
            lines.append(f"Error:          {res.error}")
        else:
            lines.append(
                f"Successfully notified {res.server_type} library rescan at {res.endpoint}"
            )
        typer.echo("\n".join(lines))
    raise typer.Exit(code=EXIT_SUCCESS if res.success else 1)


review_app = typer.Typer(
    name="review",
    help="Review and manage unrecognized media items.",
    invoke_without_command=True,
    add_completion=False,
)


def _get_review_dir(review_dir: Path | None, config_path: Path | None) -> Path:
    if review_dir is not None:
        return review_dir
    cfg = MediaCronConfig.load(config_path=config_path)
    if cfg.paths.review_dir is not None:
        return cfg.paths.review_dir
    typer.echo(
        "Error: --review-dir must be specified via CLI or config file.",
        err=True,
    )
    raise typer.Exit(code=2)


def _is_interactive() -> bool:
    import sys

    return sys.stdin.isatty()


@review_app.callback(invoke_without_command=True)
def review_interactive(
    ctx: typer.Context,
    review_dir: Path | None = typer.Option(
        None, "--review-dir", help="Directory containing staged review items"
    ),
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Path to YAML configuration file"
    ),
) -> None:
    """Interactive guided review session for pending items."""
    if ctx.invoked_subcommand is not None:
        return

    if not _is_interactive():
        typer.echo(
            "Error: Interactive review requires an interactive terminal (TTY). "
            "Use 'media-cron review list' or non-interactive subcommands instead.",
            err=True,
        )
        raise typer.Exit(code=1)

    target_review_dir = _get_review_dir(review_dir, config)
    cfg = MediaCronConfig.load(config_path=config)

    from media_cron.review.manager import ReviewManager
    from media_cron.review.models import ReviewAction, ReviewStatus, UserAnnotation

    manager = ReviewManager(review_dir=target_review_dir)
    pending_items = manager.list_items(status=ReviewStatus.PENDING)

    if not pending_items:
        typer.echo("No items pending review.")
        raise typer.Exit(code=EXIT_SUCCESS)

    typer.echo(f"Found {len(pending_items)} item(s) pending review in {target_review_dir}:\n")

    for item in pending_items:
        typer.echo(f"=== Review Item: {item.item_id} ===")
        typer.echo(f"  Original: {item.original_path}")
        typer.echo(f"  Files:    {len(item.files)} file(s), {item.total_size_bytes} bytes")
        if item.failure_reasons:
            typer.echo(f"  Failures: {', '.join(item.failure_reasons)}")

        hint = item.detected_category_hint or "movie"
        category = typer.prompt("Category", default=hint)
        title = typer.prompt("Title", default="")
        year_str = typer.prompt("Year", default="")
        creator = typer.prompt("Creator/Artist/Author", default="")

        action_choice = typer.prompt(
            "Action: [O]rganize Now, [R]eturn to Staging, [D]iscard, [S]kip, [Q]uit",
            default="s",
        )
        choice = action_choice.strip().lower()
        if choice.startswith("q"):
            typer.echo("Exiting review session.")
            break
        elif choice.startswith("s"):
            typer.echo(f"Skipped {item.item_id}.")
            continue
        elif choice.startswith("o"):
            year = int(year_str) if year_str.isdigit() else None
            annotation = UserAnnotation(
                category=category,
                title=title,
                year=year,
                creator=creator if creator else None,
            )
            manager.resolve_item(
                item_id=item.item_id,
                annotation=annotation,
                action=ReviewAction.ORGANIZE_NOW,
                config=cfg,
            )
            typer.echo(f"Organized {item.item_id}.")
        elif choice.startswith("r"):
            year = int(year_str) if year_str.isdigit() else None
            annotation = UserAnnotation(
                category=category,
                title=title,
                year=year,
                creator=creator if creator else None,
            )
            manager.resolve_item(
                item_id=item.item_id,
                annotation=annotation,
                action=ReviewAction.REINGEST,
                config=cfg,
            )
            typer.echo(f"Returned {item.item_id} to staging.")
        elif choice.startswith("d"):
            confirm = typer.confirm(
                f"Are you sure you want to discard {item.item_id}?", default=False
            )
            if confirm:
                annotation = UserAnnotation(
                    category=category,
                    title=title,
                )
                manager.resolve_item(
                    item_id=item.item_id,
                    annotation=annotation,
                    action=ReviewAction.DISCARD,
                    config=cfg,
                )
                typer.echo(f"Discarded {item.item_id}.")
            else:
                typer.echo(f"Skipped discarding {item.item_id}.")


@review_app.command("list")
def review_list(
    status: str = typer.Option(
        "pending",
        "--status",
        help="Filter items by status: pending, resolved, reingested, discarded, all",
    ),
    review_dir: Path | None = typer.Option(
        None, "--review-dir", help="Directory containing staged review items"
    ),
    format: str = typer.Option(
        "text", "--format", "-f", help="Output display format: text or json"
    ),
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Path to YAML configuration file"
    ),
) -> None:
    """Lists items staged in the review directory."""
    from media_cron.review.manager import ReviewManager
    from media_cron.review.models import ReviewStatus

    target_review_dir = _get_review_dir(review_dir, config)
    manager = ReviewManager(review_dir=target_review_dir)

    filter_status: ReviewStatus | None = None
    if status.lower() != "all":
        try:
            filter_status = ReviewStatus(status.lower())
        except ValueError:
            msg = (
                f"Invalid status: {status}. Allowed: pending, resolved, reingested, discarded, all"
            )
            if format.lower() == "json":
                typer.echo(json.dumps({"error": msg, "exit_code": 2}))
            else:
                typer.echo(f"Error: {msg}", err=True)
            raise typer.Exit(code=2) from None

    items = manager.list_items(status=filter_status)

    if format.lower() == "json":
        typer.echo(json.dumps([m.to_dict() for m in items], indent=2))
    else:
        lines = [
            "=== Staged Review Items ===",
            f"Review Directory: {target_review_dir}",
            f"Total Items:     {len(items)}",
            "--------------------------------------------------------------------------------",
        ]
        if not items:
            lines.append("No items found.")
        else:
            for item in items:
                files_str = ", ".join(f.relative_path.name for f in item.files)
                lines.append(
                    f"ID:       {item.item_id}\n"
                    f"Files:    {files_str} ({item.original_path})\n"
                    f"Category: {item.detected_category_hint or 'unknown'}\n"
                    f"Status:   {item.status.value}\n"
                    f"Size:     {item.total_size_bytes} bytes\n"
                    f"Created:  {item.created_at.isoformat()}\n"
                    "--------------------------------------------------------------------------------"
                )
        typer.echo("\n".join(lines))
    raise typer.Exit(code=EXIT_SUCCESS)


@review_app.command("show")
def review_show(
    item_id: str = typer.Argument(..., help="ID of review item to inspect"),
    review_dir: Path | None = typer.Option(
        None, "--review-dir", help="Directory containing staged review items"
    ),
    format: str = typer.Option(
        "text", "--format", "-f", help="Output display format: text or json"
    ),
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Path to YAML configuration file"
    ),
) -> None:
    """Displays detailed manifest and files for a specific review item."""
    from media_cron.review.manager import ReviewManager

    target_review_dir = _get_review_dir(review_dir, config)
    manager = ReviewManager(review_dir=target_review_dir)

    try:
        manifest = manager.get_item(item_id)
    except FileNotFoundError as e:
        if format.lower() == "json":
            typer.echo(json.dumps({"error": str(e), "exit_code": 1}))
        else:
            typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1) from e

    if format.lower() == "json":
        typer.echo(json.dumps(manifest.to_dict(), indent=2))
    else:
        lines = [
            f"=== Review Item: {manifest.item_id} ===",
            f"Original Path: {manifest.original_path}",
            f"Is Directory:  {manifest.is_directory}",
            f"Status:        {manifest.status.value}",
            f"Category Hint: {manifest.detected_category_hint or 'None'}",
            f"Total Size:    {manifest.total_size_bytes} bytes",
            f"Created At:    {manifest.created_at.isoformat()}",
        ]
        if manifest.failure_reasons:
            lines.append("Failure Reasons:")
            for r in manifest.failure_reasons:
                lines.append(f"  - {r}")
        lines.append("Contained Files:")
        for f in manifest.files:
            lines.append(f"  - {f.relative_path} ({f.size_bytes} bytes)")
        if manifest.user_annotation:
            lines.append("User Annotation:")
            ann = manifest.user_annotation
            lines.append(f"  Category: {ann.category}")
            lines.append(f"  Title:    {ann.title}")
            if ann.creator:
                lines.append(f"  Creator:  {ann.creator}")
            if ann.year:
                lines.append(f"  Year:     {ann.year}")
        typer.echo("\n".join(lines))
    raise typer.Exit(code=EXIT_SUCCESS)


@review_app.command("resolve")
def review_resolve(
    item_id: str = typer.Argument(..., help="ID of review item to resolve"),
    category: str = typer.Option(
        ..., "--category", help="Target category (movie, tv, music, book, audiobook)"
    ),
    title: str = typer.Option(..., "--title", help="Title of the media asset"),
    creator: str | None = typer.Option(None, "--creator", help="Creator/Artist/Author"),
    year: int | None = typer.Option(None, "--year", help="Release year"),
    season: int | None = typer.Option(None, "--season", help="Season number (for TV)"),
    episode: int | None = typer.Option(None, "--episode", help="Episode number (for TV)"),
    action: str = typer.Option(
        "organize", "--action", help="Action to execute: organize or reingest"
    ),
    review_dir: Path | None = typer.Option(
        None, "--review-dir", help="Directory containing staged review items"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Simulate without writing files"),
    format: str = typer.Option("text", "--format", "-f", help="Output format: text or json"),
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Path to YAML configuration file"
    ),
) -> None:
    """Applies user metadata and executes resolution action (organize or reingest)."""
    from media_cron.review.manager import ReviewManager
    from media_cron.review.models import ReviewAction, UserAnnotation

    act = action.lower()
    if act in ("organize", "organize_now"):
        rev_action = ReviewAction.ORGANIZE_NOW
    elif act == "reingest":
        rev_action = ReviewAction.REINGEST
    else:
        msg = f"Invalid action: {action}. Allowed: organize, reingest"
        if format.lower() == "json":
            typer.echo(json.dumps({"error": msg, "exit_code": 2}))
        else:
            typer.echo(f"Error: {msg}", err=True)
        raise typer.Exit(code=2)

    target_review_dir = _get_review_dir(review_dir, config)
    cfg = MediaCronConfig.load(config_path=config)
    manager = ReviewManager(review_dir=target_review_dir)

    annotation = UserAnnotation(
        category=category,
        title=title,
        creator=creator,
        year=year,
        season=season,
        episode=episode,
    )

    try:
        manifest = manager.resolve_item(
            item_id=item_id,
            annotation=annotation,
            action=rev_action,
            config=cfg,
            dry_run=dry_run,
        )
    except FileNotFoundError as e:
        if format.lower() == "json":
            typer.echo(json.dumps({"error": str(e), "exit_code": 1}))
        else:
            typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1) from e

    if format.lower() == "json":
        typer.echo(json.dumps(manifest.to_dict(), indent=2))
    else:
        typer.echo(f"Successfully resolved item '{item_id}' with action '{act}'.")
    raise typer.Exit(code=EXIT_SUCCESS)


@review_app.command("discard")
def review_discard(
    item_id: str = typer.Argument(..., help="ID of review item to discard"),
    force: bool = typer.Option(False, "--force", help="Force discard without confirmation"),
    review_dir: Path | None = typer.Option(
        None, "--review-dir", help="Directory containing staged review items"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Simulate without deleting files"),
    format: str = typer.Option("text", "--format", "-f", help="Output format: text or json"),
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Path to YAML configuration file"
    ),
) -> None:
    """Deletes an item from the review directory."""
    from media_cron.review.manager import ReviewManager
    from media_cron.review.models import ReviewAction, UserAnnotation

    if not force:
        if not _is_interactive():
            msg = "Error: --force is required in non-interactive mode to discard items."
            if format.lower() == "json":
                typer.echo(json.dumps({"error": msg, "exit_code": 1}))
            else:
                typer.echo(msg, err=True)
            raise typer.Exit(code=1)
        confirm = typer.confirm(
            f"Are you sure you want to discard review item '{item_id}'?", default=False
        )
        if not confirm:
            typer.echo("Discard cancelled.")
            raise typer.Exit(code=EXIT_SUCCESS)

    target_review_dir = _get_review_dir(review_dir, config)
    cfg = MediaCronConfig.load(config_path=config)
    manager = ReviewManager(review_dir=target_review_dir)

    try:
        manager.resolve_item(
            item_id=item_id,
            annotation=UserAnnotation(category="discarded", title="discarded"),
            action=ReviewAction.DISCARD,
            config=cfg,
            dry_run=dry_run,
        )
    except FileNotFoundError as e:
        if format.lower() == "json":
            typer.echo(json.dumps({"error": str(e), "exit_code": 1}))
        else:
            typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1) from e

    if format.lower() == "json":
        typer.echo(
            json.dumps(
                {"status": "discarded", "item_id": item_id, "dry_run": dry_run},
                indent=2,
            )
        )
    else:
        typer.echo(f"Discarded review item '{item_id}'.")
    raise typer.Exit(code=EXIT_SUCCESS)


@review_app.command("purge")
def review_purge(
    older_than: int = typer.Option(
        ..., "--older-than", help="Purge items older than this number of days"
    ),
    force: bool = typer.Option(False, "--force", help="Force purge without confirmation"),
    review_dir: Path | None = typer.Option(
        None, "--review-dir", help="Directory containing staged review items"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Simulate without deleting files"),
    format: str = typer.Option("text", "--format", "-f", help="Output format: text or json"),
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Path to YAML configuration file"
    ),
) -> None:
    """Purges items staged longer than the specified age in days."""
    from media_cron.review.manager import ReviewManager

    if not force:
        if not _is_interactive():
            msg = "Error: --force is required in non-interactive mode to purge items."
            if format.lower() == "json":
                typer.echo(json.dumps({"error": msg, "exit_code": 1}))
            else:
                typer.echo(msg, err=True)
            raise typer.Exit(code=1)
        confirm = typer.confirm(
            f"Are you sure you want to purge items older than {older_than} day(s)?",
            default=False,
        )
        if not confirm:
            typer.echo("Purge cancelled.")
            raise typer.Exit(code=EXIT_SUCCESS)

    target_review_dir = _get_review_dir(review_dir, config)
    manager = ReviewManager(review_dir=target_review_dir)

    purged_ids = manager.purge_items(older_than_days=older_than, dry_run=dry_run)

    if format.lower() == "json":
        typer.echo(
            json.dumps(
                {
                    "status": "success",
                    "purged_count": len(purged_ids),
                    "purged_items": purged_ids,
                    "older_than_days": older_than,
                    "dry_run": dry_run,
                },
                indent=2,
            )
        )
    else:
        action_word = "Would purge" if dry_run else "Purged"
        typer.echo(f"{action_word} {len(purged_ids)} item(s) older than {older_than} day(s).")
    raise typer.Exit(code=EXIT_SUCCESS)


app.add_typer(review_app, name="review")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
