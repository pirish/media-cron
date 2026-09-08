import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

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
    lookups: list[str] = field(default_factory=lambda: ["scene_video", "audio_tag", "book_meta"])
    outputs: list[str] = field(
        default_factory=lambda: ["library_organizer", "seed_relocator", "junk_cleaner"]
    )


@dataclass
class MediaCronConfig:
    paths: PathsConfig = field(default_factory=PathsConfig)
    general: GeneralConfig = field(default_factory=GeneralConfig)
    templates: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_TEMPLATES))
    plugins: PluginsConfig = field(default_factory=PluginsConfig)
    active_torrent_client: str | None = None
    hybrid_ingest: bool = False
    torrent_clients: dict[str, TorrentClientConfig] = field(default_factory=dict)

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

        return cfg
