from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class TorrentState(StrEnum):
    DOWNLOADING = "downloading"
    SEEDING = "seeding"
    COMPLETED = "completed"
    PAUSED = "paused"
    CHECKING = "checking"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass
class TorrentFile:
    name: str
    size: int
    progress: float = 1.0


@dataclass
class TorrentItem:
    info_hash: str
    name: str
    total_size: int
    progress: float
    state: TorrentState
    save_path: str
    content_path: str
    category: str = ""
    tags: list[str] = field(default_factory=list)
    files: list[TorrentFile] = field(default_factory=list)

    def is_completed(self) -> bool:
        """Returns True if torrent has reached 100% download progress."""
        return self.progress >= 1.0 and self.state in (
            TorrentState.SEEDING,
            TorrentState.COMPLETED,
            TorrentState.PAUSED,
        )

    def is_healthy(self) -> bool:
        """Returns True if torrent is not checking, downloading, or in an error state."""
        return self.state not in (
            TorrentState.ERROR,
            TorrentState.CHECKING,
            TorrentState.UNKNOWN,
        )


@dataclass
class PathMappingRule:
    remote_prefix: str
    local_prefix: str

    def translate(self, remote_path: str | Path) -> Path:
        """Translates a remote client path into a local filesystem path."""
        path_str = str(remote_path)
        # Normalize trailing slashes for clean prefix replacement
        rem_prefix = self.remote_prefix.rstrip("/")
        loc_prefix = self.local_prefix.rstrip("/")

        if path_str == rem_prefix or path_str.startswith(rem_prefix + "/"):
            remainder = path_str[len(rem_prefix) :].lstrip("/")
            return Path(loc_prefix) / remainder if remainder else Path(loc_prefix)
        return Path(path_str)


@dataclass
class TorrentFilterConfig:
    categories: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    exclude_tags: list[str] = field(default_factory=lambda: ["media-cron-processed"])
    exclude_categories: list[str] = field(default_factory=lambda: ["media-cron-done"])
    min_progress: float = 1.0

    def matches(self, torrent: TorrentItem) -> bool:
        """Evaluates whether a torrent satisfies ingestion filter rules."""
        if torrent.progress < self.min_progress:
            return False

        if not torrent.is_completed() or not torrent.is_healthy():
            return False

        # Exclude already processed categories or tags
        if self.exclude_categories and torrent.category in self.exclude_categories:
            return False

        for tag in torrent.tags:
            if tag in self.exclude_tags:
                return False

        # Category check
        if self.categories and torrent.category not in self.categories:
            return False

        # Required tags check
        if self.tags:
            if not any(tag in torrent.tags for tag in self.tags):
                return False

        return True


@dataclass
class TorrentSeedingConfig:
    mode: str = "client_relocate"  # client_relocate | direct_filesystem | none
    target_location: str = "seed_dir"  # seed_dir | destination_dir
    completion_tag: str = "media-cron-processed"
    completion_category: str = "media-cron-done"
    pause_after_process: bool = False


@dataclass
class TorrentClientConfig:
    client_type: str = "qbittorrent"
    host: str = "localhost"
    port: int = 8080
    username: str | None = None
    password: str | None = None
    use_ssl: bool = False
    timeout: float = 10.0
    path_mappings: list[PathMappingRule] = field(default_factory=list)
    filters: TorrentFilterConfig = field(default_factory=TorrentFilterConfig)
    seeding: TorrentSeedingConfig = field(default_factory=TorrentSeedingConfig)

    def translate_path(self, remote_path: str | Path) -> Path:
        """Translates a remote path using configured mapping rules in order."""
        for rule in self.path_mappings:
            translated = rule.translate(remote_path)
            if translated != Path(remote_path):
                return translated
        return Path(remote_path)

    def __repr__(self) -> str:
        pwd_repr = "***" if self.password else "None"
        return (
            f"TorrentClientConfig(client_type={self.client_type!r}, host={self.host!r}, "
            f"port={self.port}, username={self.username!r}, password={pwd_repr}, "
            f"use_ssl={self.use_ssl}, timeout={self.timeout})"
        )
