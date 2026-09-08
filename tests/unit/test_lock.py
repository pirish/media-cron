from pathlib import Path

import pytest

from media_cron.lock import LockContentionError, StagingLock


def test_lock_acquire_and_release(tmp_path: Path):
    staging_dir = tmp_path / "staging"
    lock = StagingLock(staging_dir)

    with lock:
        assert lock.lock_path.exists()
        assert lock._fd is not None

    assert lock._fd is None


def test_lock_contention_raises_error(tmp_path: Path):
    staging_dir = tmp_path / "staging"
    lock1 = StagingLock(staging_dir)
    lock2 = StagingLock(staging_dir)

    with lock1:
        with pytest.raises(LockContentionError) as exc_info:
            lock2.acquire()
        assert "currently locked by another process" in str(exc_info.value)

    # After lock1 exits, lock2 can acquire successfully
    with lock2:
        assert lock2._fd is not None
