import logging
import time
import urllib.error
import urllib.request

from media_cron.metadata.base import MediaServerClientProtocol
from media_cron.metadata.models import MediaServerConfig, MediaServerRescanResult

logger = logging.getLogger(__name__)


class BaseMediaServerClient(MediaServerClientProtocol):
    """Base class for HTTP-based media server library rescan clients with retry and resilience."""

    @property
    def server_type(self) -> str:
        raise NotImplementedError("Subclasses must define server_type")

    def _build_request(
        self,
        config: MediaServerConfig,
        library_id: str | None = None,
        path: str | None = None,
    ) -> urllib.request.Request:
        """Constructs the urllib Request object for the specific media server endpoint."""
        raise NotImplementedError("Subclasses must define _build_request")

    def trigger_rescan(
        self,
        config: MediaServerConfig,
        library_id: str | None = None,
        path: str | None = None,
        dry_run: bool = False,
    ) -> MediaServerRescanResult:
        """Dispatches an authenticated rescan request with retry handling and non-fatal errors."""
        try:
            req = self._build_request(config, library_id, path)
        except Exception as e:
            logger.warning("Failed to construct %s rescan request: %s", self.server_type, e)
            return MediaServerRescanResult(
                server_type=self.server_type,
                endpoint=config.url,
                status_code=None,
                duration_seconds=0.0,
                success=False,
                error=str(e),
            )

        endpoint = req.full_url
        if dry_run:
            logger.info(
                "[DRY-RUN] Simulated %s library rescan targeting: %s", self.server_type, endpoint
            )
            return MediaServerRescanResult(
                server_type=self.server_type,
                endpoint=endpoint,
                status_code=204,
                duration_seconds=0.0,
                success=True,
            )

        timeout = config.timeout_seconds if config.timeout_seconds > 0 else 5.0
        max_retries = max(0, config.max_retries)
        total_attempts = 1 + max_retries

        start_time = time.perf_counter()
        last_error: str | None = None
        last_code: int | None = None

        for attempt in range(total_attempts):
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    status = resp.status
                    duration = time.perf_counter() - start_time
                    logger.info(
                        "Successfully notified %s library rescan at %s (HTTP %d, %.2fs)",
                        self.server_type,
                        endpoint,
                        status,
                        duration,
                    )
                    return MediaServerRescanResult(
                        server_type=self.server_type,
                        endpoint=endpoint,
                        status_code=status,
                        duration_seconds=duration,
                        success=True,
                    )
            except urllib.error.HTTPError as e:
                last_code = e.code
                last_error = f"HTTP {e.code}: {e.reason}"
                logger.warning(
                    "%s library rescan attempt %d/%d failed with HTTP %d: %s",
                    self.server_type,
                    attempt + 1,
                    total_attempts,
                    e.code,
                    e.reason,
                )
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                last_code = None
                last_error = str(e)
                logger.warning(
                    "%s library rescan attempt %d/%d connection error: %s",
                    self.server_type,
                    attempt + 1,
                    total_attempts,
                    e,
                )
            except Exception as e:
                last_code = None
                last_error = f"Unexpected error: {e}"
                logger.warning(
                    "%s library rescan attempt %d/%d unexpected exception: %s",
                    self.server_type,
                    attempt + 1,
                    total_attempts,
                    e,
                )

            if attempt < total_attempts - 1:
                sleep_delay = 0.25 * (2**attempt)
                time.sleep(sleep_delay)

        total_duration = time.perf_counter() - start_time
        logger.warning(
            "%s library rescan failed after %d attempt(s): %s",
            self.server_type,
            total_attempts,
            last_error,
        )
        return MediaServerRescanResult(
            server_type=self.server_type,
            endpoint=endpoint,
            status_code=last_code,
            duration_seconds=total_duration,
            success=False,
            error=last_error,
        )
