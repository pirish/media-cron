from __future__ import annotations

import shlex
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class TransferError(RuntimeError):
    """Base exception for file transfer engine errors."""


class TransferConfigError(ValueError):
    """Raised when a TransferConfig or custom command template is invalid."""


class TransferDiskFullError(TransferError):
    """Raised when destination storage lacks sufficient free space (ENOSPC)."""


class TransferTimeoutError(TransferError):
    """Raised when an external transfer command exceeds timeout_seconds."""


class TransferExecutionError(TransferError):
    """Raised when a transfer fails and fallback is disabled or also fails."""


class TransferStrategy(StrEnum):
    NATIVE = "native"
    CUSTOM = "custom"
    BUILTIN = "builtin"

    @classmethod
    def from_str(cls, value: str | TransferStrategy) -> TransferStrategy:
        if isinstance(value, TransferStrategy):
            return value
        normalized = str(value).strip().lower()
        for member in cls:
            if member.value == normalized:
                return member
        raise TransferConfigError(
            f"Unsupported transfer strategy '{value}'. Expected one of: native, custom, builtin."
        )


class TransferAction(StrEnum):
    COPY = "copy"
    MOVE = "move"


def _validate_command_template(template: str | None, field_name: str) -> None:
    if template is None:
        return
    stripped = template.strip()
    if not stripped:
        raise TransferConfigError(f"{field_name} cannot be an empty string.")
    try:
        tokens = shlex.split(stripped)
    except ValueError as err:
        raise TransferConfigError(f"Invalid command template in {field_name}: {err}") from err

    if not tokens:
        raise TransferConfigError(f"{field_name} must contain at least an executable name.")

    has_src = any("{src}" in t for t in tokens)
    has_dst = any("{dst}" in t for t in tokens)
    if has_src != has_dst:
        raise TransferConfigError(
            f"Custom command template in {field_name} must include both {{src}} and {{dst}} "
            "placeholders, or omit both for positional appending."
        )


@dataclass
class TransferConfig:
    strategy: TransferStrategy = TransferStrategy.NATIVE
    copy_command: str | None = None
    move_command: str | None = None
    fallback_enabled: bool = True
    timeout_seconds: float = 3600.0

    def __post_init__(self) -> None:
        self.strategy = TransferStrategy.from_str(self.strategy)
        self.fallback_enabled = bool(self.fallback_enabled)
        self.timeout_seconds = float(self.timeout_seconds)
        if self.timeout_seconds <= 0:
            raise TransferConfigError("timeout_seconds must be greater than 0")
        _validate_command_template(self.copy_command, "copy_command")
        _validate_command_template(self.move_command, "move_command")

    @classmethod
    def from_dict(
        cls,
        data: dict | None,
        base: TransferConfig | None = None,
    ) -> TransferConfig:
        defaults = base or cls()
        if not data or not isinstance(data, dict):
            return cls(
                strategy=defaults.strategy,
                copy_command=defaults.copy_command,
                move_command=defaults.move_command,
                fallback_enabled=defaults.fallback_enabled,
                timeout_seconds=defaults.timeout_seconds,
            )

        copy_cmd = data.get("copy_command", defaults.copy_command)
        move_cmd = data.get("move_command", defaults.move_command)
        if "strategy" in data and data["strategy"] is not None:
            strategy = TransferStrategy.from_str(data["strategy"])
        elif ("copy_command" in data and copy_cmd) or ("move_command" in data and move_cmd):
            strategy = TransferStrategy.CUSTOM
        else:
            strategy = defaults.strategy

        fallback = (
            bool(data["fallback_enabled"])
            if "fallback_enabled" in data and data["fallback_enabled"] is not None
            else defaults.fallback_enabled
        )
        timeout = (
            float(data["timeout_seconds"])
            if "timeout_seconds" in data and data["timeout_seconds"] is not None
            else defaults.timeout_seconds
        )
        return cls(
            strategy=strategy,
            copy_command=copy_cmd,
            move_command=move_cmd,
            fallback_enabled=fallback,
            timeout_seconds=timeout,
        )


@dataclass
class TransferOperation:
    src: Path
    dst: Path
    action: TransferAction
    configured_strategy: TransferStrategy
    dry_run: bool = False
    source_bytes: int = 0


@dataclass
class TransferOutcome:
    src: Path
    dst: Path
    action: TransferAction
    configured_strategy: TransferStrategy
    effective_strategy: TransferStrategy
    fallback_used: bool = False
    fallback_reason: str | None = None
    command_executed: list[str] | None = None
    bytes_transferred: int = 0
    duration_ms: float = 0.0
    throughput_mbps: float = 0.0
    dry_run: bool = False

    def to_dict(self) -> dict:
        return {
            "src": str(self.src),
            "dst": str(self.dst),
            "action": self.action.value,
            "configured_strategy": self.configured_strategy.value,
            "effective_strategy": self.effective_strategy.value,
            "fallback_used": self.fallback_used,
            "fallback_reason": self.fallback_reason,
            "command_executed": list(self.command_executed) if self.command_executed else None,
            "bytes_transferred": self.bytes_transferred,
            "duration_ms": round(self.duration_ms, 3),
            "throughput_mbps": round(self.throughput_mbps, 3),
            "dry_run": self.dry_run,
        }


@dataclass
class TransferSummary:
    native_count: int = 0
    custom_count: int = 0
    builtin_count: int = 0
    fallback_count: int = 0
    total_bytes_transferred: int = 0
    total_duration_ms: float = 0.0

    def record(self, outcome: TransferOutcome) -> None:
        if outcome.effective_strategy == TransferStrategy.NATIVE:
            self.native_count += 1
        elif outcome.effective_strategy == TransferStrategy.CUSTOM:
            self.custom_count += 1
        else:
            self.builtin_count += 1

        if outcome.fallback_used:
            self.fallback_count += 1

        self.total_bytes_transferred += outcome.bytes_transferred
        self.total_duration_ms += outcome.duration_ms

    def to_dict(self) -> dict:
        return {
            "native_count": self.native_count,
            "custom_count": self.custom_count,
            "builtin_count": self.builtin_count,
            "fallback_count": self.fallback_count,
            "total_bytes_transferred": self.total_bytes_transferred,
            "total_duration_ms": round(self.total_duration_ms, 3),
        }
