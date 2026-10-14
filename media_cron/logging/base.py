import logging
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from media_cron.logging.models import LoggingConfig


@runtime_checkable
class LoggingEngineProtocol(Protocol):
    """Core protocol for configuring and managing application-wide logging."""

    def setup(self, config: "LoggingConfig") -> None:
        """
        Initializes handlers, formatters, and filters based on LoggingConfig.
        Ensures idempotency (clearing existing handlers before adding new ones).
        Creates parent directories for file targets if required.
        Raises ConfigurationError or ValueError if configuration or destination is invalid.
        """
        ...

    def get_effective_config(self) -> "LoggingConfig":
        """Returns the currently active LoggingConfig instance."""
        ...

    def reset(self) -> None:
        """Flushes and closes all handlers and restores default Python logging state."""
        ...


@runtime_checkable
class LogFormatterProtocol(Protocol):
    """Protocol for transforming LogRecord instances into serialized output."""

    def format(self, record: logging.LogRecord) -> str:
        """Formats the specified LogRecord into a text or JSON string."""
        ...


@runtime_checkable
class SensitiveDataSanitizerProtocol(Protocol):
    """Protocol for scrubbing sensitive patterns from log messages and attributes."""

    def sanitize_message(self, message: str) -> str:
        """Returns the sanitized message string with sensitive tokens masked."""
        ...

    def filter(self, record: logging.LogRecord) -> bool:
        """Standard logging.Filter method to redact record in-place."""
        ...
