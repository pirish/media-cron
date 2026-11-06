import pytest

from media_cron.transfer.models import (
    TransferAction,
    TransferConfig,
    TransferConfigError,
    TransferDiskFullError,
    TransferError,
    TransferExecutionError,
    TransferOperation,
    TransferOutcome,
    TransferStrategy,
    TransferSummary,
    TransferTimeoutError,
)


def test_transfer_enums() -> None:
    assert TransferStrategy.NATIVE.value == "native"
    assert TransferStrategy.CUSTOM.value == "custom"
    assert TransferStrategy.BUILTIN.value == "builtin"
    assert TransferStrategy.from_str("NATIVE") == TransferStrategy.NATIVE
    assert TransferStrategy.from_str("custom") == TransferStrategy.CUSTOM
    assert TransferStrategy.from_str("builtin") == TransferStrategy.BUILTIN

    with pytest.raises(TransferConfigError, match="Unsupported transfer strategy"):
        TransferStrategy.from_str("invalid_strategy")

    assert TransferAction.COPY.value == "copy"
    assert TransferAction.MOVE.value == "move"


def test_transfer_config_defaults_and_validation() -> None:
    cfg = TransferConfig()
    assert cfg.strategy == TransferStrategy.NATIVE
    assert cfg.copy_command is None
    assert cfg.move_command is None
    assert cfg.fallback_enabled is True
    assert cfg.timeout_seconds == 3600.0

    # String coercion for strategy
    cfg_custom = TransferConfig(
        strategy="custom",  # type: ignore[arg-type]
        copy_command="rsync -a {src} {dst}",
        move_command="rsync -a --remove-source-files {src} {dst}",
        fallback_enabled=False,
        timeout_seconds=120.0,
    )
    assert cfg_custom.strategy == TransferStrategy.CUSTOM
    assert cfg_custom.fallback_enabled is False
    assert cfg_custom.timeout_seconds == 120.0


def test_transfer_config_invalid_values() -> None:
    with pytest.raises(TransferConfigError, match="timeout_seconds must be greater than 0"):
        TransferConfig(timeout_seconds=0)

    with pytest.raises(TransferConfigError, match="timeout_seconds must be greater than 0"):
        TransferConfig(timeout_seconds=-10.0)

    # Unbalanced quotes in custom template
    with pytest.raises(TransferConfigError, match="Invalid command template"):
        TransferConfig(
            strategy=TransferStrategy.CUSTOM, copy_command="rsync -a 'unclosed {src} {dst}"
        )

    # Only one placeholder provided
    with pytest.raises(TransferConfigError, match="must include both \\{src\\} and \\{dst\\}"):
        TransferConfig(strategy=TransferStrategy.CUSTOM, copy_command="rsync -a {src}")

    with pytest.raises(TransferConfigError, match="must include both \\{src\\} and \\{dst\\}"):
        TransferConfig(strategy=TransferStrategy.CUSTOM, move_command="rsync -a {dst}")


def test_transfer_config_merge_override() -> None:
    base = TransferConfig(
        strategy=TransferStrategy.NATIVE,
        copy_command=None,
        move_command=None,
        fallback_enabled=True,
        timeout_seconds=3600.0,
    )
    override = TransferConfig.from_dict(
        {"strategy": "custom", "copy_command": "cp -r {src} {dst}"},
        base=base,
    )
    assert override.strategy == TransferStrategy.CUSTOM
    assert override.copy_command == "cp -r {src} {dst}"
    assert override.move_command is None
    assert override.fallback_enabled is True
    assert override.timeout_seconds == 3600.0


def test_transfer_operation_and_outcome_models(tmp_path) -> None:
    src = tmp_path / "src.mkv"
    dst = tmp_path / "dst.mkv"
    op = TransferOperation(
        src=src,
        dst=dst,
        action=TransferAction.COPY,
        configured_strategy=TransferStrategy.NATIVE,
        dry_run=False,
        source_bytes=104857600,
    )
    assert op.src == src
    assert op.dst == dst
    assert op.action == TransferAction.COPY
    assert op.source_bytes == 104857600

    outcome = TransferOutcome(
        src=src,
        dst=dst,
        action=TransferAction.COPY,
        configured_strategy=TransferStrategy.NATIVE,
        effective_strategy=TransferStrategy.NATIVE,
        fallback_used=False,
        fallback_reason=None,
        command_executed=["cp", "-r", "--reflink=auto", str(src), str(dst)],
        bytes_transferred=104857600,
        duration_ms=500.0,
        throughput_mbps=200.0,
        dry_run=False,
    )
    assert outcome.throughput_mbps == 200.0
    d = outcome.to_dict()
    assert d["effective_strategy"] == "native"
    assert d["bytes_transferred"] == 104857600


def test_transfer_summary_aggregation(tmp_path) -> None:
    summary = TransferSummary()
    src = tmp_path / "a.mkv"
    dst = tmp_path / "b.mkv"

    summary.record(
        TransferOutcome(
            src=src,
            dst=dst,
            action=TransferAction.COPY,
            configured_strategy=TransferStrategy.NATIVE,
            effective_strategy=TransferStrategy.NATIVE,
            fallback_used=False,
            fallback_reason=None,
            command_executed=["cp", "-r", "--reflink=auto", str(src), str(dst)],
            bytes_transferred=1000,
            duration_ms=10.0,
            throughput_mbps=0.1,
            dry_run=False,
        )
    )
    summary.record(
        TransferOutcome(
            src=src,
            dst=dst,
            action=TransferAction.MOVE,
            configured_strategy=TransferStrategy.CUSTOM,
            effective_strategy=TransferStrategy.BUILTIN,
            fallback_used=True,
            fallback_reason="Tool missing",
            command_executed=["my-tool", str(src), str(dst)],
            bytes_transferred=2000,
            duration_ms=25.0,
            throughput_mbps=0.08,
            dry_run=False,
        )
    )

    assert summary.native_count == 1
    assert summary.custom_count == 0
    assert summary.builtin_count == 1
    assert summary.fallback_count == 1
    assert summary.total_bytes_transferred == 3000
    assert summary.total_duration_ms == 35.0
    assert summary.to_dict() == {
        "native_count": 1,
        "custom_count": 0,
        "builtin_count": 1,
        "fallback_count": 1,
        "total_bytes_transferred": 3000,
        "total_duration_ms": 35.0,
    }


def test_transfer_exception_hierarchy() -> None:
    assert issubclass(TransferConfigError, ValueError)
    assert issubclass(TransferDiskFullError, TransferError)
    assert issubclass(TransferTimeoutError, TransferError)
    assert issubclass(TransferExecutionError, TransferError)
