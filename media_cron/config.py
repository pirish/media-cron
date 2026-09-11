import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from media_cron.metadata.models import MediaServerConfig
from media_cron.torrent.models import (
    PathMappingRule,
    TorrentClientConfig,
    TorrentFilterConfig,
    TorrentSeedingConfig,
)

DEFAULT_JUNK_EXTENSIONS = [
    ".nfo",
    ".txt",
    ".url",
    ".sfv",
    ".exe",
    ".m3u",
    ".website",
]

DEFAULT_TEMPLATES = {
    "movie": "Movies/{title} ({year})/{title} ({year}).{ext}",
    "series": "TV Shows/{show}/Season {season:02d}/{show} - S{season:02d}E{episode:02d}.{ext}",
    "music": "Music/{artist}/{album}/{track:02d} - {title}.{ext}",
    "audiobook": "Audiobooks/{author}/{title}/{track:02d} - {title}.{ext}",
    "book": "Books/{author}/{title}.{ext}",
}


@dataclass
class PathsConfig:
    source_dir: Path | None = None
    staging_dir: Path = field(default_factory=lambda: Path.home() / ".media-cron" / "staging")
    destination_dir: Path | None = None
    seed_dir: Path | None = None
    review_dir: Path | None = None


@dataclass
class GeneralConfig:
    mode: str = "hardlink"
    dry_run: bool = False
    lockfile_timeout_seconds: int = 0
    sample_size_threshold_mb: int = 50
    junk_extensions: list[str] = field(default_factory=lambda: list(DEFAULT_JUNK_EXTENSIONS))


@dataclass
class PluginsConfig:
    input: str = "directory_scanner"
    lookups: list[str] = field(
        default_factory=lambda: ["scene_video", "music", "audio_tag", "book_meta"]
    )
    outputs: list[str] = field(
        default_factory=lambda: ["library_organizer", "seed_relocator", "junk_cleaner"]
    )


@dataclass
class ExternalProviderConfig:
    provider_name: str
    enabled: bool = True
    priority: int = 10
    base_url: str = ""
    api_key: str | None = None
    timeout_seconds: float = 5.0
    rate_limit_delay: float = 1.0


@dataclass
class MetadataCacheConfig:
    enabled: bool = True
    ttl_seconds: int = 2592000  # 30 days
    cache_file: Path = field(
        default_factory=lambda: Path(".media-cron-cache") / "audiobook_cache.json"
    )


def default_audiobook_providers() -> dict[str, ExternalProviderConfig]:
    return {
        "openlibrary": ExternalProviderConfig(
            provider_name="openlibrary",
            enabled=True,
            priority=10,
            base_url="https://openlibrary.org",
            timeout_seconds=5.0,
            rate_limit_delay=1.0,
        ),
        "audnexus": ExternalProviderConfig(
            provider_name="audnexus",
            enabled=False,
            priority=20,
            base_url="https://api.audnexus.com",
            timeout_seconds=5.0,
            rate_limit_delay=0.5,
        ),
    }


def default_book_providers() -> dict[str, ExternalProviderConfig]:
    return {
        "openlibrary": ExternalProviderConfig(
            provider_name="openlibrary",
            enabled=True,
            priority=10,
            base_url="https://openlibrary.org",
            timeout_seconds=5.0,
            rate_limit_delay=0.5,
        ),
    }


@dataclass
class UDCConfig:
    enabled: bool = False
    min_confidence: float = 0.70
    summary_table_path: Path | None = None


@dataclass
class BookConversionConfig:
    enabled: bool = False
    preferred_engine: str = "calibre"
    timeout_seconds: int = 120
    retention_policy: str = "preserve"
    archive_dir: Path | None = None
    inject_metadata: bool = True


@dataclass
class BooksConfig:
    enabled: bool = True
    enable_external_lookup: bool = True
    confidence_threshold: float = 0.85
    udc_lookup: UDCConfig = field(default_factory=UDCConfig)
    conversion: BookConversionConfig = field(default_factory=BookConversionConfig)
    cache: MetadataCacheConfig = field(
        default_factory=lambda: MetadataCacheConfig(
            cache_file=Path(".media-cron-cache") / "book_cache.json"
        )
    )
    providers: dict[str, ExternalProviderConfig] = field(default_factory=default_book_providers)


@dataclass
class AudiobookConfig:
    enable_external_lookup: bool = True
    confidence_threshold: float = 0.85
    cache: MetadataCacheConfig = field(default_factory=MetadataCacheConfig)
    providers: dict[str, ExternalProviderConfig] = field(
        default_factory=default_audiobook_providers
    )


def default_music_providers() -> dict[str, ExternalProviderConfig]:
    return {
        "musicbrainz": ExternalProviderConfig(
            provider_name="musicbrainz",
            enabled=True,
            priority=10,
            base_url="https://musicbrainz.org/ws/2",
            timeout_seconds=10.0,
            rate_limit_delay=1.0,
        ),
        "discogs": ExternalProviderConfig(
            provider_name="discogs",
            enabled=False,
            priority=20,
            base_url="https://api.discogs.com",
            timeout_seconds=10.0,
            rate_limit_delay=1.0,
        ),
    }


@dataclass
class MusicConfig:
    enabled: bool = True
    workflow_mode: str = "direct"  # "spool" | "direct" | "hybrid"
    spool_dir: Path | None = None
    post_ingest_command: str | None = None
    post_command_timeout_seconds: int = 120
    library_dir: str = "Music"
    path_template: str = "{artist}/{album} ({year})/{track:02d} - {title}.{ext}"
    compilation_artist: str = "Various Artists"
    enable_external_lookup: bool = False
    provider: str = "musicbrainz"
    discogs_token: str | None = None
    confidence_threshold: float = 0.85
    hardlink_with_copy_fallback: bool = True
    preserve_companions: bool = True
    cache: MetadataCacheConfig = field(
        default_factory=lambda: MetadataCacheConfig(
            cache_file=Path(".media-cron-cache") / "music_cache.json"
        )
    )
    providers: dict[str, ExternalProviderConfig] = field(default_factory=default_music_providers)


@dataclass
class VideoConfig:
    enabled: bool = True
    workflow_mode: str = "direct"  # "spool" | "direct" | "hybrid"
    spool_dir: Path | None = None
    post_ingest_command: str | None = None
    post_command_timeout_seconds: int = 120
    preserve_companions: bool = True
    library_movies_dir: str = "Movies"
    library_tv_dir: str = "TV"
    movie_path_template: str = (
        "{library_movies_dir}/{title} ({year})/{title} ({year}) [{resolution}].{ext}"
    )
    tv_path_template: str = "{library_tv_dir}/{show}/Season {season:02d}/{show} - S{season:02d}E{episode:02d} - {title} [{resolution}].{ext}"
    media_server: MediaServerConfig = field(default_factory=MediaServerConfig)


@dataclass
class ReviewConfig:
    enabled: bool = True
    max_age_days: int = 0


@dataclass
class MediaCronConfig:
    paths: PathsConfig = field(default_factory=PathsConfig)
    general: GeneralConfig = field(default_factory=GeneralConfig)
    templates: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_TEMPLATES))
    plugins: PluginsConfig = field(default_factory=PluginsConfig)
    active_torrent_client: str | None = None
    hybrid_ingest: bool = False
    torrent_clients: dict[str, TorrentClientConfig] = field(default_factory=dict)
    audiobook: AudiobookConfig = field(default_factory=AudiobookConfig)
    books: BooksConfig = field(default_factory=BooksConfig)
    music: MusicConfig = field(default_factory=MusicConfig)
    video: VideoConfig = field(default_factory=lambda: VideoConfig(enabled=False))
    review: ReviewConfig = field(default_factory=ReviewConfig)

    @classmethod
    def load(cls, config_path: Path | None = None) -> "MediaCronConfig":
        """Loads configuration from YAML file and applies environment overrides."""
        cfg = cls()

        # 1. Resolve configuration file path
        if not config_path:
            env_cfg = os.getenv("MEDIA_CRON_CONFIG")
            if env_cfg:
                config_path = Path(env_cfg)
            else:
                default_path = Path.home() / ".config" / "media-cron" / "config.yaml"
                if default_path.exists():
                    config_path = default_path

        # 2. Parse YAML if file exists
        if config_path and config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            if "active_torrent_client" in data:
                cfg.active_torrent_client = data["active_torrent_client"]
            if "hybrid_ingest" in data:
                cfg.hybrid_ingest = bool(data["hybrid_ingest"])

            if "paths" in data:
                p = data["paths"]
                if "source_dir" in p and p["source_dir"]:
                    cfg.paths.source_dir = Path(p["source_dir"])
                if "staging_dir" in p and p["staging_dir"]:
                    cfg.paths.staging_dir = Path(p["staging_dir"])
                if "destination_dir" in p and p["destination_dir"]:
                    cfg.paths.destination_dir = Path(p["destination_dir"])
                if "seed_dir" in p and p["seed_dir"]:
                    cfg.paths.seed_dir = Path(p["seed_dir"])
                if "review_dir" in p and p["review_dir"]:
                    cfg.paths.review_dir = Path(p["review_dir"])

            if "review" in data and isinstance(data["review"], dict):
                r = data["review"]
                if "enabled" in r:
                    cfg.review.enabled = bool(r["enabled"])
                if "max_age_days" in r:
                    cfg.review.max_age_days = int(r["max_age_days"])

            if "general" in data:
                g = data["general"]
                if "mode" in g:
                    cfg.general.mode = g["mode"]
                if "dry_run" in g:
                    cfg.general.dry_run = bool(g["dry_run"])
                if "lockfile_timeout_seconds" in g:
                    cfg.general.lockfile_timeout_seconds = int(g["lockfile_timeout_seconds"])
                if "sample_size_threshold_mb" in g:
                    cfg.general.sample_size_threshold_mb = int(g["sample_size_threshold_mb"])
                if "junk_extensions" in g:
                    cfg.general.junk_extensions = list(g["junk_extensions"])

            if "templates" in data and isinstance(data["templates"], dict):
                cfg.templates.update(data["templates"])

            if "plugins" in data:
                pl = data["plugins"]
                if "input" in pl:
                    cfg.plugins.input = pl["input"]
                if "lookups" in pl:
                    cfg.plugins.lookups = list(pl["lookups"])
                if "outputs" in pl:
                    cfg.plugins.outputs = list(pl["outputs"])

            if "torrent_clients" in data and isinstance(data["torrent_clients"], dict):
                for name, cdata in data["torrent_clients"].items():
                    pms = [
                        PathMappingRule(r["remote_prefix"], r["local_prefix"])
                        for r in cdata.get("path_mappings", [])
                    ]
                    fdata = cdata.get("filters", {})
                    filters = TorrentFilterConfig(
                        categories=list(fdata.get("categories", [])),
                        tags=list(fdata.get("tags", [])),
                        exclude_tags=list(fdata.get("exclude_tags", ["media-cron-processed"])),
                        exclude_categories=list(
                            fdata.get("exclude_categories", ["media-cron-done"])
                        ),
                        min_progress=float(fdata.get("min_progress", 1.0)),
                    )
                    sdata = cdata.get("seeding", {})
                    seeding = TorrentSeedingConfig(
                        mode=str(sdata.get("mode", "client_relocate")),
                        target_location=str(sdata.get("target_location", "seed_dir")),
                        completion_tag=str(sdata.get("completion_tag", "media-cron-processed")),
                        completion_category=str(
                            sdata.get("completion_category", "media-cron-done")
                        ),
                        pause_after_process=bool(sdata.get("pause_after_process", False)),
                    )
                    client_cfg = TorrentClientConfig(
                        client_type=str(cdata.get("client_type", name)),
                        host=str(cdata.get("host", "localhost")),
                        port=int(cdata.get("port", 8080)),
                        username=cdata.get("username"),
                        password=cdata.get("password"),
                        use_ssl=bool(cdata.get("use_ssl", False)),
                        timeout=float(cdata.get("timeout", 10.0)),
                        path_mappings=pms,
                        filters=filters,
                        seeding=seeding,
                    )
                    cfg.torrent_clients[name] = client_cfg

            if "audiobook" in data and isinstance(data["audiobook"], dict):
                ab = data["audiobook"]
                if "enable_external_lookup" in ab:
                    cfg.audiobook.enable_external_lookup = bool(ab["enable_external_lookup"])
                if "confidence_threshold" in ab:
                    cfg.audiobook.confidence_threshold = float(ab["confidence_threshold"])
                if "cache" in ab and isinstance(ab["cache"], dict):
                    c = ab["cache"]
                    if "enabled" in c:
                        cfg.audiobook.cache.enabled = bool(c["enabled"])
                    if "ttl_seconds" in c:
                        cfg.audiobook.cache.ttl_seconds = int(c["ttl_seconds"])
                    if "cache_file" in c and c["cache_file"]:
                        cfg.audiobook.cache.cache_file = Path(c["cache_file"])
                if "providers" in ab and isinstance(ab["providers"], dict):
                    for pname, pdata in ab["providers"].items():
                        prov_cfg = cfg.audiobook.providers.get(
                            pname, ExternalProviderConfig(provider_name=pname)
                        )
                        if "enabled" in pdata:
                            prov_cfg.enabled = bool(pdata["enabled"])
                        if "priority" in pdata:
                            prov_cfg.priority = int(pdata["priority"])
                        if "base_url" in pdata:
                            prov_cfg.base_url = str(pdata["base_url"])
                        if "api_key" in pdata:
                            prov_cfg.api_key = pdata["api_key"]
                        if "timeout_seconds" in pdata:
                            prov_cfg.timeout_seconds = float(pdata["timeout_seconds"])
                        if "rate_limit_delay" in pdata:
                            prov_cfg.rate_limit_delay = float(pdata["rate_limit_delay"])
                        cfg.audiobook.providers[pname] = prov_cfg

            if "books" in data and isinstance(data["books"], dict):
                bk = data["books"]
                if "enabled" in bk:
                    cfg.books.enabled = bool(bk["enabled"])
                if "enable_external_lookup" in bk:
                    cfg.books.enable_external_lookup = bool(bk["enable_external_lookup"])
                if "confidence_threshold" in bk:
                    cfg.books.confidence_threshold = float(bk["confidence_threshold"])
                if "udc_lookup" in bk and isinstance(bk["udc_lookup"], dict):
                    udc = bk["udc_lookup"]
                    if "enabled" in udc:
                        cfg.books.udc_lookup.enabled = bool(udc["enabled"])
                    if "min_confidence" in udc:
                        cfg.books.udc_lookup.min_confidence = float(udc["min_confidence"])
                    if "summary_table_path" in udc and udc["summary_table_path"]:
                        cfg.books.udc_lookup.summary_table_path = Path(udc["summary_table_path"])
                if "conversion" in bk and isinstance(bk["conversion"], dict):
                    conv = bk["conversion"]
                    if "enabled" in conv:
                        cfg.books.conversion.enabled = bool(conv["enabled"])
                    if "preferred_engine" in conv:
                        cfg.books.conversion.preferred_engine = str(conv["preferred_engine"])
                    if "timeout_seconds" in conv:
                        cfg.books.conversion.timeout_seconds = int(conv["timeout_seconds"])
                    if "retention_policy" in conv:
                        cfg.books.conversion.retention_policy = str(conv["retention_policy"])
                    if "archive_dir" in conv and conv["archive_dir"]:
                        cfg.books.conversion.archive_dir = Path(conv["archive_dir"])
                    if "inject_metadata" in conv:
                        cfg.books.conversion.inject_metadata = bool(conv["inject_metadata"])
                if "cache" in bk and isinstance(bk["cache"], dict):
                    c = bk["cache"]
                    if "enabled" in c:
                        cfg.books.cache.enabled = bool(c["enabled"])
                    if "ttl_seconds" in c:
                        cfg.books.cache.ttl_seconds = int(c["ttl_seconds"])
                    if "cache_file" in c and c["cache_file"]:
                        cfg.books.cache.cache_file = Path(c["cache_file"])
                if "providers" in bk and isinstance(bk["providers"], dict):
                    for pname, pdata in bk["providers"].items():
                        prov_cfg = cfg.books.providers.get(
                            pname, ExternalProviderConfig(provider_name=pname)
                        )
                        if "enabled" in pdata:
                            prov_cfg.enabled = bool(pdata["enabled"])
                        if "priority" in pdata:
                            prov_cfg.priority = int(pdata["priority"])
                        if "base_url" in pdata:
                            prov_cfg.base_url = str(pdata["base_url"])
                        if "api_key" in pdata:
                            prov_cfg.api_key = pdata["api_key"]
                        if "timeout_seconds" in pdata:
                            prov_cfg.timeout_seconds = float(pdata["timeout_seconds"])
                        if "rate_limit_delay" in pdata:
                            prov_cfg.rate_limit_delay = float(pdata["rate_limit_delay"])
                        cfg.books.providers[pname] = prov_cfg

            if "music" in data and isinstance(data["music"], dict):
                m = data["music"]
                if "enabled" in m:
                    cfg.music.enabled = bool(m["enabled"])
                if "workflow_mode" in m:
                    cfg.music.workflow_mode = str(m["workflow_mode"])
                if "spool_dir" in m and m["spool_dir"]:
                    cfg.music.spool_dir = Path(m["spool_dir"])
                if "post_ingest_command" in m:
                    cfg.music.post_ingest_command = m["post_ingest_command"]
                if "post_command_timeout_seconds" in m:
                    cfg.music.post_command_timeout_seconds = int(m["post_command_timeout_seconds"])
                if "library_dir" in m:
                    cfg.music.library_dir = str(m["library_dir"])
                if "path_template" in m:
                    cfg.music.path_template = str(m["path_template"])
                if "compilation_artist" in m:
                    cfg.music.compilation_artist = str(m["compilation_artist"])
                if "enable_external_lookup" in m:
                    cfg.music.enable_external_lookup = bool(m["enable_external_lookup"])
                if "provider" in m:
                    cfg.music.provider = str(m["provider"])
                if "discogs_token" in m:
                    cfg.music.discogs_token = m["discogs_token"]
                if "confidence_threshold" in m:
                    cfg.music.confidence_threshold = float(m["confidence_threshold"])
                if "hardlink_with_copy_fallback" in m:
                    cfg.music.hardlink_with_copy_fallback = bool(m["hardlink_with_copy_fallback"])
                if "preserve_companions" in m:
                    cfg.music.preserve_companions = bool(m["preserve_companions"])
                if "cache" in m and isinstance(m["cache"], dict):
                    c = m["cache"]
                    if "enabled" in c:
                        cfg.music.cache.enabled = bool(c["enabled"])
                    if "ttl_seconds" in c:
                        cfg.music.cache.ttl_seconds = int(c["ttl_seconds"])
                    if "cache_file" in c and c["cache_file"]:
                        cfg.music.cache.cache_file = Path(c["cache_file"])
                if "providers" in m and isinstance(m["providers"], dict):
                    for pname, pdata in m["providers"].items():
                        prov_cfg = cfg.music.providers.get(
                            pname, ExternalProviderConfig(provider_name=pname)
                        )
                        if "enabled" in pdata:
                            prov_cfg.enabled = bool(pdata["enabled"])
                        if "priority" in pdata:
                            prov_cfg.priority = int(pdata["priority"])
                        if "base_url" in pdata:
                            prov_cfg.base_url = str(pdata["base_url"])
                        if "api_key" in pdata:
                            prov_cfg.api_key = pdata["api_key"]
                        if "timeout_seconds" in pdata:
                            prov_cfg.timeout_seconds = float(pdata["timeout_seconds"])
                        if "rate_limit_delay" in pdata:
                            prov_cfg.rate_limit_delay = float(pdata["rate_limit_delay"])
                        cfg.music.providers[pname] = prov_cfg

            if "video" in data and isinstance(data["video"], dict):
                v = data["video"]
                cfg.video.enabled = bool(v.get("enabled", True))
                if "workflow_mode" in v:
                    cfg.video.workflow_mode = str(v["workflow_mode"])
                if "spool_dir" in v and v["spool_dir"]:
                    cfg.video.spool_dir = Path(v["spool_dir"])
                if "post_ingest_command" in v:
                    cfg.video.post_ingest_command = v["post_ingest_command"]
                if "post_command_timeout_seconds" in v:
                    cfg.video.post_command_timeout_seconds = int(v["post_command_timeout_seconds"])
                if "preserve_companions" in v:
                    cfg.video.preserve_companions = bool(v["preserve_companions"])
                if "library_movies_dir" in v:
                    cfg.video.library_movies_dir = str(v["library_movies_dir"])
                if "library_tv_dir" in v:
                    cfg.video.library_tv_dir = str(v["library_tv_dir"])
                if "movie_path_template" in v:
                    cfg.video.movie_path_template = str(v["movie_path_template"])
                if "tv_path_template" in v:
                    cfg.video.tv_path_template = str(v["tv_path_template"])
                if "media_server" in v and isinstance(v["media_server"], dict):
                    ms = v["media_server"]
                    if "enabled" in ms:
                        cfg.video.media_server.enabled = bool(ms["enabled"])
                    if "provider" in ms:
                        cfg.video.media_server.provider = str(ms["provider"]).lower()
                    if "url" in ms:
                        cfg.video.media_server.url = str(ms["url"])
                    if "token" in ms:
                        cfg.video.media_server.token = str(ms["token"])
                    if "library_id" in ms:
                        cfg.video.media_server.library_id = ms["library_id"]
                    if "timeout_seconds" in ms:
                        cfg.video.media_server.timeout_seconds = float(ms["timeout_seconds"])
                    if "max_retries" in ms:
                        cfg.video.media_server.max_retries = int(ms["max_retries"])

        # 3. Apply Environment Overrides
        env_source = os.getenv("MEDIA_CRON_SOURCE_DIR")
        if env_source:
            cfg.paths.source_dir = Path(env_source)

        env_staging = os.getenv("MEDIA_CRON_STAGING_DIR")
        if env_staging:
            cfg.paths.staging_dir = Path(env_staging)

        env_dest = os.getenv("MEDIA_CRON_DESTINATION_DIR")
        if env_dest:
            cfg.paths.destination_dir = Path(env_dest)

        env_seed = os.getenv("MEDIA_CRON_SEED_DIR")
        if env_seed:
            cfg.paths.seed_dir = Path(env_seed)

        env_review = os.getenv("MEDIA_CRON_PATHS_REVIEW_DIR") or os.getenv("MEDIA_CRON_REVIEW_DIR")
        if env_review:
            cfg.paths.review_dir = Path(env_review)

        env_review_enabled = os.getenv("MEDIA_CRON_REVIEW_ENABLED")
        if env_review_enabled is not None:
            cfg.review.enabled = env_review_enabled.lower() in ("true", "1", "yes")

        env_review_max_age = os.getenv("MEDIA_CRON_REVIEW_MAX_AGE_DAYS")
        if env_review_max_age is not None:
            cfg.review.max_age_days = int(env_review_max_age)

        env_mode = os.getenv("MEDIA_CRON_MODE")
        if env_mode:
            cfg.general.mode = env_mode

        env_dry = os.getenv("MEDIA_CRON_DRY_RUN")
        if env_dry is not None:
            cfg.general.dry_run = env_dry.lower() in ("true", "1", "yes")

        env_client = os.getenv("MEDIA_CRON_ACTIVE_TORRENT_CLIENT")
        if env_client:
            cfg.active_torrent_client = env_client

        env_hybrid = os.getenv("MEDIA_CRON_HYBRID_INGEST")
        if env_hybrid is not None:
            cfg.hybrid_ingest = env_hybrid.lower() in ("true", "1", "yes")

        # Specific qBittorrent environment overrides
        qb_host = os.getenv("MEDIA_CRON_QBITTORRENT_HOST")
        qb_port = os.getenv("MEDIA_CRON_QBITTORRENT_PORT")
        qb_user = os.getenv("MEDIA_CRON_QBITTORRENT_USERNAME")
        qb_pass = os.getenv("MEDIA_CRON_QBITTORRENT_PASSWORD")
        qb_seed_mode = os.getenv("MEDIA_CRON_SEEDING_MODE")
        qb_tag = os.getenv("MEDIA_CRON_COMPLETION_TAG")
        qb_cat = os.getenv("MEDIA_CRON_COMPLETION_CATEGORY")

        if any([qb_host, qb_port, qb_user, qb_pass, qb_seed_mode, qb_tag, qb_cat]):
            if "qbittorrent" not in cfg.torrent_clients:
                cfg.torrent_clients["qbittorrent"] = TorrentClientConfig(client_type="qbittorrent")
            qb = cfg.torrent_clients["qbittorrent"]
            if qb_host:
                qb.host = qb_host
            if qb_port:
                qb.port = int(qb_port)
            if qb_user:
                qb.username = qb_user
            if qb_pass:
                qb.password = qb_pass
            if qb_seed_mode:
                qb.seeding.mode = qb_seed_mode
            if qb_tag:
                qb.seeding.completion_tag = qb_tag
            if qb_cat:
                qb.seeding.completion_category = qb_cat

        # Audiobook environment overrides
        env_ab_lookup = os.getenv("MEDIA_CRON_AUDIOBOOK_ENABLE_LOOKUP")
        if env_ab_lookup is not None:
            cfg.audiobook.enable_external_lookup = env_ab_lookup.lower() in ("true", "1", "yes")

        env_ab_thresh = os.getenv("MEDIA_CRON_AUDIOBOOK_CONFIDENCE_THRESHOLD")
        if env_ab_thresh is not None:
            cfg.audiobook.confidence_threshold = float(env_ab_thresh)

        env_cache_enabled = os.getenv("MEDIA_CRON_AUDIOBOOK_CACHE_ENABLED")
        if env_cache_enabled is not None:
            cfg.audiobook.cache.enabled = env_cache_enabled.lower() in ("true", "1", "yes")

        env_cache_ttl = os.getenv("MEDIA_CRON_AUDIOBOOK_CACHE_TTL")
        if env_cache_ttl is not None:
            cfg.audiobook.cache.ttl_seconds = int(env_cache_ttl)

        env_cache_file = os.getenv("MEDIA_CRON_AUDIOBOOK_CACHE_FILE")
        if env_cache_file is not None:
            cfg.audiobook.cache.cache_file = Path(env_cache_file)

        env_ol_enabled = os.getenv("MEDIA_CRON_OPENLIBRARY_ENABLED")
        if env_ol_enabled is not None:
            if "openlibrary" in cfg.audiobook.providers:
                cfg.audiobook.providers["openlibrary"].enabled = env_ol_enabled.lower() in (
                    "true",
                    "1",
                    "yes",
                )

        env_aud_enabled = os.getenv("MEDIA_CRON_AUDNEXUS_ENABLED")
        if env_aud_enabled is not None:
            if "audnexus" in cfg.audiobook.providers:
                cfg.audiobook.providers["audnexus"].enabled = env_aud_enabled.lower() in (
                    "true",
                    "1",
                    "yes",
                )

        env_ol_timeout = os.getenv("MEDIA_CRON_OPENLIBRARY_TIMEOUT")
        if env_ol_timeout is not None:
            if "openlibrary" in cfg.audiobook.providers:
                cfg.audiobook.providers["openlibrary"].timeout_seconds = float(env_ol_timeout)

        env_aud_timeout = os.getenv("MEDIA_CRON_AUDNEXUS_TIMEOUT")
        if env_aud_timeout is not None:
            if "audnexus" in cfg.audiobook.providers:
                cfg.audiobook.providers["audnexus"].timeout_seconds = float(env_aud_timeout)

        # Books environment overrides
        env_books_enabled = os.getenv("MEDIA_CRON_BOOKS_ENABLED")
        if env_books_enabled is not None:
            cfg.books.enabled = env_books_enabled.lower() in ("true", "1", "yes")

        env_books_lookup = os.getenv("MEDIA_CRON_BOOKS_EXTERNAL_LOOKUP")
        if env_books_lookup is not None:
            cfg.books.enable_external_lookup = env_books_lookup.lower() in ("true", "1", "yes")

        env_books_thresh = os.getenv("MEDIA_CRON_BOOKS_CONFIDENCE_THRESHOLD")
        if env_books_thresh is not None:
            cfg.books.confidence_threshold = float(env_books_thresh)

        env_books_udc = os.getenv("MEDIA_CRON_BOOKS_UDC_ENABLED")
        if env_books_udc is not None:
            cfg.books.udc_lookup.enabled = env_books_udc.lower() in ("true", "1", "yes")

        env_books_conv = os.getenv("MEDIA_CRON_BOOKS_CONVERT_EPUB")
        if env_books_conv is not None:
            cfg.books.conversion.enabled = env_books_conv.lower() in ("true", "1", "yes")

        env_books_engine = os.getenv("MEDIA_CRON_BOOKS_CONVERSION_ENGINE")
        if env_books_engine is not None:
            cfg.books.conversion.preferred_engine = env_books_engine

        env_books_retention = os.getenv("MEDIA_CRON_BOOKS_RETENTION_POLICY")
        if env_books_retention is not None:
            cfg.books.conversion.retention_policy = env_books_retention

        env_books_archive = os.getenv("MEDIA_CRON_BOOKS_ARCHIVE_DIR")
        if env_books_archive is not None:
            cfg.books.conversion.archive_dir = Path(env_books_archive)

        env_books_cache_file = os.getenv("MEDIA_CRON_BOOKS_CACHE_FILE")
        if env_books_cache_file is not None:
            cfg.books.cache.cache_file = Path(env_books_cache_file)

        env_books_cache_ttl = os.getenv("MEDIA_CRON_BOOKS_CACHE_TTL")
        if env_books_cache_ttl is not None:
            cfg.books.cache.ttl_seconds = int(env_books_cache_ttl)

        # Music environment overrides
        env_music_enabled = os.getenv("MEDIA_CRON_MUSIC_ENABLED")
        if env_music_enabled is not None:
            cfg.music.enabled = env_music_enabled.lower() in ("true", "1", "yes")

        env_music_mode = os.getenv("MEDIA_CRON_MUSIC_MODE")
        if env_music_mode is not None:
            cfg.music.workflow_mode = env_music_mode.lower()

        env_music_spool_dir = os.getenv("MEDIA_CRON_MUSIC_SPOOL_DIR")
        if env_music_spool_dir is not None:
            cfg.music.spool_dir = Path(env_music_spool_dir)

        env_music_post_cmd = os.getenv("MEDIA_CRON_MUSIC_POST_COMMAND")
        if env_music_post_cmd is not None:
            cfg.music.post_ingest_command = env_music_post_cmd

        env_music_lookup = os.getenv("MEDIA_CRON_MUSIC_LOOKUP")
        if env_music_lookup is not None:
            cfg.music.enable_external_lookup = env_music_lookup.lower() in ("true", "1", "yes")

        env_music_provider = os.getenv("MEDIA_CRON_MUSIC_PROVIDER")
        if env_music_provider is not None:
            cfg.music.provider = env_music_provider.lower()

        env_discogs_token = os.getenv("MEDIA_CRON_DISCOGS_TOKEN")
        if env_discogs_token is not None:
            cfg.music.discogs_token = env_discogs_token

        env_music_thresh = os.getenv("MEDIA_CRON_MUSIC_CONFIDENCE_THRESHOLD")
        if env_music_thresh is not None:
            cfg.music.confidence_threshold = float(env_music_thresh)

        env_music_companions = os.getenv("MEDIA_CRON_MUSIC_PRESERVE_COMPANIONS")
        if env_music_companions is not None:
            cfg.music.preserve_companions = env_music_companions.lower() in ("true", "1", "yes")

        # Dynamic default resolution: if spool_dir is set and mode wasn't explicitly given
        is_mode_explicit = env_music_mode is not None or (
            "data" in locals()
            and isinstance(data, dict)
            and "music" in data
            and "workflow_mode" in data["music"]
        )
        if cfg.music.spool_dir and not is_mode_explicit:
            cfg.music.workflow_mode = "spool"

        # Video environment overrides
        env_video_enabled = os.getenv("MEDIA_CRON_VIDEO_ENABLED")
        if env_video_enabled is not None:
            cfg.video.enabled = env_video_enabled.lower() in ("true", "1", "yes")
        elif any(
            os.getenv(k) is not None
            for k in (
                "MEDIA_CRON_VIDEO_MODE",
                "MEDIA_CRON_VIDEO_SPOOL_DIR",
                "MEDIA_CRON_VIDEO_POST_COMMAND",
                "MEDIA_CRON_MEDIA_SERVER_ENABLED",
            )
        ):
            cfg.video.enabled = True

        env_video_mode = os.getenv("MEDIA_CRON_VIDEO_MODE")
        if env_video_mode is not None:
            cfg.video.workflow_mode = env_video_mode.lower()

        env_video_spool_dir = os.getenv("MEDIA_CRON_VIDEO_SPOOL_DIR")
        if env_video_spool_dir is not None:
            cfg.video.spool_dir = Path(env_video_spool_dir)

        env_video_post_cmd = os.getenv("MEDIA_CRON_VIDEO_POST_COMMAND")
        if env_video_post_cmd is not None:
            cfg.video.post_ingest_command = env_video_post_cmd

        env_video_companions = os.getenv("MEDIA_CRON_VIDEO_PRESERVE_COMPANIONS")
        if env_video_companions is not None:
            cfg.video.preserve_companions = env_video_companions.lower() in ("true", "1", "yes")

        env_ms_enabled = os.getenv("MEDIA_CRON_MEDIA_SERVER_ENABLED")
        if env_ms_enabled is not None:
            cfg.video.media_server.enabled = env_ms_enabled.lower() in ("true", "1", "yes")

        env_ms_provider = os.getenv("MEDIA_CRON_MEDIA_SERVER_PROVIDER")
        if env_ms_provider is not None:
            cfg.video.media_server.provider = env_ms_provider.lower()

        env_ms_url = os.getenv("MEDIA_CRON_MEDIA_SERVER_URL")
        if env_ms_url is not None:
            cfg.video.media_server.url = env_ms_url

        env_ms_token = os.getenv("MEDIA_CRON_MEDIA_SERVER_TOKEN")
        if env_ms_token is not None:
            cfg.video.media_server.token = env_ms_token

        env_ms_lib = os.getenv("MEDIA_CRON_MEDIA_SERVER_LIBRARY_ID")
        if env_ms_lib is not None:
            cfg.video.media_server.library_id = env_ms_lib

        env_ms_retries = os.getenv("MEDIA_CRON_MEDIA_SERVER_MAX_RETRIES")
        if env_ms_retries is not None:
            cfg.video.media_server.max_retries = int(env_ms_retries)

        # Dynamic default resolution: if spool_dir is set and mode wasn't explicitly given
        is_video_mode_explicit = env_video_mode is not None or (
            "data" in locals()
            and isinstance(data, dict)
            and "video" in data
            and "workflow_mode" in data["video"]
        )
        if cfg.video.spool_dir and not is_video_mode_explicit:
            cfg.video.workflow_mode = "spool"

        return cfg
