import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

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

        return cfg
