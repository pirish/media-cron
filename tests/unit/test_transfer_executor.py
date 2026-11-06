import subprocess
from collections import namedtuple
from pathlib import Path
from unittest.mock import patch

import pytest

from media_cron.transfer.executor import FileTransferExecutor
from media_cron.transfer.models import (
    TransferAction,
    TransferConfig,
    TransferDiskFullError,
    TransferExecutionError,
    TransferStrategy,
    TransferTimeoutError,
)


def test_native_copy_and_move_real_execution(tmp_path: Path) -> None:
    executor = FileTransferExecutor(TransferConfig(strategy=TransferStrategy.NATIVE))

    # 1. File copy
    src_file = tmp_path / "source" / "movie.mkv"
    src_file.parent.mkdir(parents=True)
    src_file.write_bytes(b"hello world" * 1024)

    dst_file = tmp_path / "dest" / "nested" / "movie.mkv"
    outcome = executor.copy(src_file, dst_file)

    assert dst_file.exists()
    assert dst_file.read_bytes() == src_file.read_bytes()
    assert src_file.exists()
    assert outcome.action == TransferAction.COPY
    assert outcome.effective_strategy == TransferStrategy.NATIVE
    assert outcome.fallback_used is False
    assert outcome.bytes_transferred == len(b"hello world" * 1024)
    assert outcome.command_executed is not None
    assert outcome.command_executed[0] == "cp"

    # 2. Directory copy
    src_dir = tmp_path / "source" / "album_dir"
    (src_dir / "disc1").mkdir(parents=True)
    (src_dir / "disc1" / "01.flac").write_bytes(b"music data" * 500)
    dst_dir = tmp_path / "dest" / "albums" / "album_dir"

    dir_outcome = executor.copy(src_dir, dst_dir)
    assert (dst_dir / "disc1" / "01.flac").exists()
    assert dir_outcome.effective_strategy == TransferStrategy.NATIVE
    assert dir_outcome.bytes_transferred == len(b"music data" * 500)

    # 3. File move
    move_dst = tmp_path / "moved" / "movie.mkv"
    move_outcome = executor.move(src_file, move_dst)
    assert move_dst.exists()
    assert not src_file.exists()
    assert move_outcome.action == TransferAction.MOVE
    assert move_outcome.effective_strategy == TransferStrategy.NATIVE
    assert move_outcome.command_executed == ["mv", str(src_file), str(move_dst)]


def test_native_copy_reflink_unsupported_retries_cp_r(tmp_path: Path) -> None:
    executor = FileTransferExecutor(TransferConfig(strategy=TransferStrategy.NATIVE))
    src = tmp_path / "test.mkv"
    src.write_bytes(b"payload")
    dst = tmp_path / "out" / "test.mkv"

    calls: list[list[str]] = []

    def fake_run(argv: list[str], **kwargs):
        calls.append(list(argv))
        assert kwargs.get("shell") is False
        if "--reflink=auto" in argv:
            return subprocess.CompletedProcess(
                args=argv,
                returncode=1,
                stdout="",
                stderr="cp: unrecognized option '--reflink=auto'",
            )
        # Second call: cp -r
        Path(argv[-1]).write_bytes(Path(argv[-2]).read_bytes())
        return subprocess.CompletedProcess(args=argv, returncode=0, stdout="", stderr="")

    with patch("subprocess.run", side_effect=fake_run):
        outcome = executor.copy(src, dst)

    assert len(calls) == 2
    assert calls[0] == ["cp", "-r", "--reflink=auto", str(src), str(dst)]
    assert calls[1] == ["cp", "-r", str(src), str(dst)]
    assert outcome.effective_strategy == TransferStrategy.NATIVE
    assert outcome.fallback_used is False
    assert dst.read_bytes() == b"payload"


def test_dry_run_does_not_execute_or_mutate(tmp_path: Path) -> None:
    executor = FileTransferExecutor(TransferConfig(strategy=TransferStrategy.NATIVE))
    src = tmp_path / "video.mkv"
    src.write_bytes(b"123456")
    dst = tmp_path / "nonexistent_parent" / "video.mkv"

    with patch("subprocess.run") as mock_run:
        outcome = executor.move(src, dst, dry_run=True)

    mock_run.assert_not_called()
    assert not dst.parent.exists()
    assert src.exists()
    assert outcome.dry_run is True
    assert outcome.command_executed == ["mv", str(src), str(dst)]


def test_custom_command_placeholders_and_special_characters(tmp_path: Path) -> None:
    special_name = "Show Name (2026) - S01E01 [1080p] & 'More' \"Quotes\"!.mkv"
    src = tmp_path / special_name
    src.write_bytes(b"special content")
    dst = tmp_path / "dest_dir" / special_name

    cfg = TransferConfig(
        strategy=TransferStrategy.CUSTOM,
        copy_command="cp -r {src} {dst}",
        move_command="cp -r",  # Positional append mode; leaves src behind so executor must clean up!
    )
    executor = FileTransferExecutor(cfg)

    copy_outcome = executor.copy(src, dst)
    assert copy_outcome.effective_strategy == TransferStrategy.CUSTOM
    assert copy_outcome.command_executed == ["cp", "-r", str(src), str(dst)]
    assert dst.exists()
    assert dst.read_bytes() == b"special content"
    assert src.exists()

    # Now test custom move where the tool (cp -r) only copies and leaves src behind:
    # Executor must verify dst exists and matches source size, then delete src!
    move_dst = tmp_path / "moved_dir" / special_name
    move_outcome = executor.move(src, move_dst)
    assert move_outcome.effective_strategy == TransferStrategy.CUSTOM
    assert move_outcome.command_executed == ["cp", "-r", str(src), str(move_dst)]
    assert move_dst.exists()
    assert move_dst.read_bytes() == b"special content"
    assert not src.exists()


def test_custom_move_directory_source_cleanup_and_size_mismatch_protection(tmp_path: Path) -> None:
    # 1. Directory move where custom command leaves directory behind
    src_dir = tmp_path / "src_album"
    src_dir.mkdir()
    (src_dir / "track1.flac").write_bytes(b"audio1" * 100)
    dst_dir = tmp_path / "dst_album"

    executor = FileTransferExecutor(
        TransferConfig(
            strategy=TransferStrategy.CUSTOM,
            move_command="cp -r {src} {dst}",
            fallback_enabled=False,
        )
    )
    outcome = executor.move(src_dir, dst_dir)
    assert outcome.effective_strategy == TransferStrategy.CUSTOM
    assert (dst_dir / "track1.flac").exists()
    assert not src_dir.exists()

    # 2. If custom move exits 0 but writes corrupted/wrong size to dst, do NOT delete src!
    src_file = tmp_path / "important.mkv"
    src_file.write_bytes(b"important_full_payload")
    bad_dst = tmp_path / "bad_dst.mkv"

    def fake_bad_move(argv: list[str], **kwargs):
        bad_dst.write_bytes(b"truncated")
        return subprocess.CompletedProcess(args=argv, returncode=0, stdout="", stderr="")

    with (
        patch("subprocess.run", side_effect=fake_bad_move),
        pytest.raises(TransferExecutionError, match="size mismatch"),
    ):
        executor.move(src_file, bad_dst)

    assert src_file.exists()
    assert not bad_dst.exists()


def test_fallback_on_missing_binary_and_nonzero_exit_cleans_partial(tmp_path: Path) -> None:
    src = tmp_path / "source.mkv"
    src.write_bytes(b"full_video_stream")
    dst = tmp_path / "target.mkv"

    # 1. Missing binary falls back to builtin
    executor = FileTransferExecutor(
        TransferConfig(
            strategy=TransferStrategy.CUSTOM,
            copy_command="nonexistent_binary_xyz {src} {dst}",
            fallback_enabled=True,
        )
    )
    outcome = executor.copy(src, dst)
    assert outcome.effective_strategy == TransferStrategy.BUILTIN
    assert outcome.fallback_used is True
    assert outcome.fallback_reason is not None
    assert dst.read_bytes() == b"full_video_stream"

    # 2. Non-zero exit after writing partial destination file: purges partial file & falls back
    dst2 = tmp_path / "target2.mkv"

    def fake_partial_fail(argv: list[str], **kwargs):
        dst2.write_bytes(b"corrupt_partial")
        return subprocess.CompletedProcess(
            args=argv, returncode=2, stdout="", stderr="transfer interrupted"
        )

    with patch("subprocess.run", side_effect=fake_partial_fail):
        outcome2 = executor.copy(src, dst2)

    assert outcome2.effective_strategy == TransferStrategy.BUILTIN
    assert outcome2.fallback_used is True
    assert dst2.read_bytes() == b"full_video_stream"


def test_timeout_and_strict_mode_no_fallback(tmp_path: Path) -> None:
    src = tmp_path / "movie.mkv"
    src.write_bytes(b"content")
    dst = tmp_path / "dest.mkv"

    def fake_timeout(argv: list[str], **kwargs):
        dst.write_bytes(b"partial_before_timeout")
        raise subprocess.TimeoutExpired(cmd=argv, timeout=1.0)

    # With fallback_enabled=False, raises TransferTimeoutError and cleans up partial dst
    strict_exec = FileTransferExecutor(
        TransferConfig(
            strategy=TransferStrategy.NATIVE,
            fallback_enabled=False,
            timeout_seconds=1.0,
        )
    )
    with (
        patch("subprocess.run", side_effect=fake_timeout),
        pytest.raises(TransferTimeoutError, match="timed out"),
    ):
        strict_exec.copy(src, dst)
    assert not dst.exists()

    # With fallback_enabled=True, recovers via builtin after cleaning up partial dst
    fallback_exec = FileTransferExecutor(
        TransferConfig(
            strategy=TransferStrategy.NATIVE,
            fallback_enabled=True,
            timeout_seconds=1.0,
        )
    )
    with patch("subprocess.run", side_effect=fake_timeout):
        outcome = fallback_exec.copy(src, dst)
    assert outcome.effective_strategy == TransferStrategy.BUILTIN
    assert outcome.fallback_used is True
    assert dst.read_bytes() == b"content"


def test_enospc_aborts_immediately_without_builtin_fallback(tmp_path: Path) -> None:
    src = tmp_path / "huge.mkv"
    src.write_bytes(b"0123456789" * 100)
    dst = tmp_path / "full_disk" / "huge.mkv"

    executor = FileTransferExecutor(
        TransferConfig(strategy=TransferStrategy.NATIVE, fallback_enabled=True)
    )

    # 1. Pre-flight disk_usage check detects insufficient free space
    DiskUsage = namedtuple("usage", ["total", "used", "free"])
    with (
        patch("shutil.disk_usage", return_value=DiskUsage(1000, 990, 10)),
        patch("shutil.copy2") as mock_builtin_copy,
        pytest.raises(TransferDiskFullError, match="No space left on device"),
    ):
        executor.copy(src, dst)
    mock_builtin_copy.assert_not_called()

    # 2. Subprocess stderr reports "No space left on device" mid-transfer
    def fake_enospc_run(argv: list[str], **kwargs):
        dst.write_bytes(b"half_written")
        return subprocess.CompletedProcess(
            args=argv,
            returncode=1,
            stdout="",
            stderr="cp: error writing 'huge.mkv': No space left on device",
        )

    with (
        patch("subprocess.run", side_effect=fake_enospc_run),
        patch("shutil.copy2") as mock_builtin_copy2,
        pytest.raises(TransferDiskFullError, match="No space left on device"),
    ):
        executor.copy(src, dst)

    mock_builtin_copy2.assert_not_called()
    assert not dst.exists()


def test_summary_and_override_config(tmp_path: Path) -> None:
    executor = FileTransferExecutor(TransferConfig(strategy=TransferStrategy.NATIVE))
    src1 = tmp_path / "f1.mkv"
    src1.write_bytes(b"aaaa")
    dst1 = tmp_path / "d1.mkv"
    executor.copy(src1, dst1)

    src2 = tmp_path / "f2.mkv"
    src2.write_bytes(b"bbbbbb")
    dst2 = tmp_path / "d2.mkv"
    executor.copy(
        src2,
        dst2,
        override_config=TransferConfig(strategy=TransferStrategy.BUILTIN),
    )

    summary = executor.get_summary()
    assert summary.native_count == 1
    assert summary.builtin_count == 1
    assert summary.custom_count == 0
    assert summary.fallback_count == 0
    assert summary.total_bytes_transferred == 10
