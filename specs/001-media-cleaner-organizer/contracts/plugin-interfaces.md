# Contract: Plugin Interfaces

This document formalizes the public Python interface contracts for the pluggable Media-Cron architecture.

---

## 1. Input Plugin Contract

An `InputPlugin` is responsible for finding raw media candidates from a source location (e.g., directory scan, torrent client API, queue) and transferring them to the staging area.

```python
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable, Protocol
from media_cron.models import DiscoveredItem


class InputPlugin(Protocol):
    """Protocol for ingesting media candidates into the pipeline."""

    @property
    def plugin_name(self) -> str:
        """Unique identifier for the input plugin."""
        ...

    def discover(self, source_path: Path, staging_path: Path) -> Iterable[DiscoveredItem]:
        """
        Discovers items from source and moves/stages them into staging_path.

        Args:
            source_path: The configured source directory or endpoint.
            staging_path: The dedicated staging directory where files must be staged.

        Returns:
            An iterable of DiscoveredItem objects located in the staging directory.

        Raises:
            PermissionError: If source or staging paths are inaccessible.
            FileNotFoundError: If source_path does not exist.
        """
        ...
```

### Built-in Default: `DirectoryScannerInput`
- Recursively walks `source_path`.
- Atomically moves raw downloaded files/folders into `staging_path`.
- Leaves `source_path` clean and ready for subsequent downloads.

---

## 2. Lookup Plugin Contract

A `LookupPlugin` is responsible for parsing filenames, reading embedded metadata, and constructing a typed `MediaAsset`.

```python
from typing import Protocol, Optional
from media_cron.models import DiscoveredItem, MediaAsset


class LookupPlugin(Protocol):
    """Protocol for extracting metadata and normalizing media assets."""

    @property
    def plugin_name(self) -> str:
        """Unique identifier for the lookup plugin."""
        ...

    def can_handle(self, item: DiscoveredItem) -> bool:
        """
        Returns True if this plugin can parse metadata for the discovered item.

        Args:
            item: The discovered item in staging.
        """
        ...

    def enrich(self, item: DiscoveredItem) -> MediaAsset:
        """
        Extracts title, category, year/season/episode, audio/book tags, and quality.

        Args:
            item: The discovered item to enrich.

        Returns:
            A populated, validated MediaAsset instance.
        """
        ...
```

### Built-in Defaults:
1. `SceneVideoLookup`: Handles `.mkv`, `.mp4`, `.avi`, `.mov`. Parses scene regex, resolves clean titles, video resolution, codecs.
2. `AudioTagLookup`: Handles `.mp3`, `.flac`, `.m4a`, `.m4b`. Reads ID3/Vorbis tags for artist, album, track number, and bitrate.
3. `BookMetaLookup`: Handles `.epub`, `.pdf`, `.mobi`. Reads book title and author metadata.

---

## 3. Output Plugin Contract

An `OutputPlugin` is responsible for executing filesystem operations to organize, seed, or prune files.

```python
from typing import Protocol, List
from media_cron.models import OperationPlan, OperationResult


class OutputPlugin(Protocol):
    """Protocol for executing file placement, seeding, or pruning."""

    @property
    def plugin_name(self) -> str:
        """Unique identifier for the output plugin."""
        ...

    def execute(self, plan: OperationPlan) -> OperationResult:
        """
        Executes a planned file operation (e.g. hardlink, atomic move, deletion).

        Args:
            plan: The operation plan specifying source, destination, mode, and dry-run.

        Returns:
            OperationResult indicating success, skipped status, or error details.
        """
        ...
```

### Built-in Defaults:
1. `LibraryOrganizerOutput`: Resolves destination path templates and executes atomic moves, hardlinks, or quality-upgrades into the target media library.
2. `SeedRelocatorOutput`: When configured with `seed_dir`, creates a hardlink or moves original material to the seed directory with original names intact.
3. `JunkCleanerOutput`: Deletes clutter files (`.nfo`, `.txt`, `.url`, samples < 50MB) and prunes empty parent directories.

---

## 4. Plugin Registry Contract

```python
from typing import Dict, Type


class PluginRegistry:
    """Central registry holding available and active plugins."""

    def register_input(self, name: str, plugin_cls: Type[InputPlugin]) -> None: ...
    def register_lookup(self, name: str, plugin_cls: Type[LookupPlugin]) -> None: ...
    def register_output(self, name: str, plugin_cls: Type[OutputPlugin]) -> None: ...

    def get_input(self, name: str) -> InputPlugin: ...
    def get_lookups(self) -> List[LookupPlugin]: ...
    def get_output(self, name: str) -> OutputPlugin: ...
```
