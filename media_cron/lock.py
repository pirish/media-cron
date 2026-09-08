import fcntl
import os
from pathlib import Path


class LockContentionError(Exception):
    """Raised when the staging directory lock is already held by another process."""

    pass


class StagingLock:
    """Non-blocking directory lockfile manager using POSIX fcntl.flock."""

    def __init__(self, staging_dir: Path, lockfile_name: str = ".media-cron.lock") -> None:
        self.staging_dir = Path(staging_dir)
        self.lock_path = self.staging_dir / lockfile_name
        self._fd: int | None = None

    def acquire(self) -> None:
        """
        Attempts to acquire an exclusive, non-blocking lock.

        Raises:
            LockContentionError: If another process already holds the lock.
        """
        self.staging_dir.mkdir(parents=True, exist_ok=True)
        try:
            self._fd = os.open(self.lock_path, os.O_CREAT | os.O_RDWR, 0o644)
            fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            # Write current PID into lockfile for diagnostics
            os.ftruncate(self._fd, 0)
            os.write(self._fd, f"{os.getpid()}\n".encode())
        except (BlockingIOError, OSError) as e:
            if self._fd is not None:
                os.close(self._fd)
                self._fd = None
            raise LockContentionError(
                f"Staging directory '{self.staging_dir}' is currently locked by another process."
            ) from e

    def release(self) -> None:
        """Releases the lock and closes file descriptor."""
        if self._fd is not None:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
            except OSError:
                pass
            finally:
                os.close(self._fd)
                self._fd = None

    def __enter__(self) -> "StagingLock":
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()
