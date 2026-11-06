from __future__ import annotations

import errno
import logging
import shlex
import shutil
import subprocess
import time
from pathlib import Path

from media_cron.transfer.base import TransferExecutorProtocol
from media_cron.transfer.models import (
    TransferAction,
    TransferConfig,
    TransferDiskFullError,
    TransferExecutionError,
    TransferOutcome,
    TransferStrategy,
    TransferSummary,
    TransferTimeoutError,
)

logger = logging.getLogger(__name__)


def compute_path_size(path: Path) -> int:
    """Compute total size in bytes of a file or directory tree."""
    if not path.exists():
        return 0
    if path.is_file() or path.is_symlink():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    total = 0
    for child in path.rglob("*"):
        if child.is_file() and not child.is_symlink():
            try:
                total += child.stat().st_size
            except OSError:
                pass
    return total


class FileTransferExecutor(TransferExecutorProtocol):
    """Executes high-speed OS-native, custom utility, and built-in fallback file transfers."""

    def __init__(self, config: TransferConfig | None = None) -> None:
        self._config = config or TransferConfig()
        self._summary = TransferSummary()

    @property
    def config(self) -> TransferConfig:
        return self._config

    def get_summary(self) -> TransferSummary:
        return self._summary

    def copy(
        self,
        src: Path,
        dst: Path,
        *,
        dry_run: bool = False,
        override_config: TransferConfig | None = None,
    ) -> TransferOutcome:
        return self._execute(
            src=Path(src),
            dst=Path(dst),
            action=TransferAction.COPY,
            dry_run=dry_run,
            override_config=override_config,
        )

    def move(
        self,
        src: Path,
        dst: Path,
        *,
        dry_run: bool = False,
        override_config: TransferConfig | None = None,
    ) -> TransferOutcome:
        return self._execute(
            src=Path(src),
            dst=Path(dst),
            action=TransferAction.MOVE,
            dry_run=dry_run,
            override_config=override_config,
        )

    @staticmethod
    def _cleanup_partial(dst: Path) -> None:
        """Remove any partial destination file or directory artifact."""
        try:
            if dst.is_symlink() or dst.is_file():
                dst.unlink(missing_ok=True)
            elif dst.exists() and dst.is_dir():
                shutil.rmtree(dst, ignore_errors=True)
        except OSError as err:
            logger.warning("Failed to clean up partial destination artifact '%s': %s", dst, err)

    @staticmethod
    def _is_enospc_error(stderr: str | None = None, exc: BaseException | None = None) -> bool:
        if isinstance(exc, OSError) and exc.errno == errno.ENOSPC:
            return True
        if exc is not None and "no space left on device" in str(exc).lower():
            return True
        if stderr:
            lowered = stderr.lower()
            if "no space left on device" in lowered or "enospc" in lowered:
                return True
        return False

    @staticmethod
    def _is_unsupported_reflink_error(stderr: str | None) -> bool:
        if not stderr:
            return False
        lowered = stderr.lower()
        if "reflink" not in lowered:
            return False
        indicators = (
            "unrecognized option",
            "invalid option",
            "illegal option",
            "unknown option",
            "not supported",
            "operation not supported",
            "unsupported",
        )
        return any(ind in lowered for ind in indicators)

    @staticmethod
    def _build_custom_argv(template: str, src: Path, dst: Path) -> list[str]:
        tokens = shlex.split(template)
        has_placeholders = any("{src}" in t or "{dst}" in t for t in tokens)
        if has_placeholders:
            resolved: list[str] = []
            for token in tokens:
                if token == "{src}":
                    resolved.append(str(src))
                elif token == "{dst}":
                    resolved.append(str(dst))
                else:
                    resolved.append(token.replace("{src}", str(src)).replace("{dst}", str(dst)))
            return resolved
        return [*tokens, str(src), str(dst)]

    def _resolve_strategy_and_argv(
        self,
        src: Path,
        dst: Path,
        action: TransferAction,
        cfg: TransferConfig,
    ) -> tuple[TransferStrategy, list[str] | None]:
        if cfg.strategy == TransferStrategy.BUILTIN:
            return TransferStrategy.BUILTIN, None

        if cfg.strategy == TransferStrategy.CUSTOM:
            tmpl = cfg.copy_command if action == TransferAction.COPY else cfg.move_command
            if tmpl:
                return TransferStrategy.CUSTOM, self._build_custom_argv(tmpl, src, dst)
            # If custom strategy is selected but only one of copy/move command was provided,
            # use native command for the unconfigured action.
            return TransferStrategy.NATIVE, self._build_native_argv(src, dst, action)

        return TransferStrategy.NATIVE, self._build_native_argv(src, dst, action)

    @staticmethod
    def _build_native_argv(src: Path, dst: Path, action: TransferAction) -> list[str]:
        if action == TransferAction.COPY:
            return ["cp", "-r", "--reflink=auto", str(src), str(dst)]
        return ["mv", str(src), str(dst)]

    def _check_disk_space(self, dst_parent: Path, source_bytes: int, dst: Path) -> None:
        if source_bytes <= 0:
            return
        try:
            usage = shutil.disk_usage(dst_parent)
        except OSError:
            return
        if usage.free < source_bytes:
            self._cleanup_partial(dst)
            raise TransferDiskFullError(
                f"No space left on device at '{dst_parent}' "
                f"(required={source_bytes} bytes, free={usage.free} bytes)"
            )

    @staticmethod
    def _run_builtin(src: Path, dst: Path, action: TransferAction) -> None:
        if action == TransferAction.COPY:
            if src.is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)
        else:
            shutil.move(str(src), str(dst))

    def _execute(
        self,
        src: Path,
        dst: Path,
        action: TransferAction,
        dry_run: bool,
        override_config: TransferConfig | None,
    ) -> TransferOutcome:
        active_cfg = override_config or self._config
        effective_primary, argv = self._resolve_strategy_and_argv(src, dst, action, active_cfg)
        source_bytes = compute_path_size(src)

        if dry_run:
            logger.info(
                "[DRY-RUN] Planned %s transfer via strategy=%s: %s -> %s (cmd=%s)",
                action.value,
                effective_primary.value,
                src,
                dst,
                argv,
            )
            return TransferOutcome(
                src=src,
                dst=dst,
                action=action,
                configured_strategy=active_cfg.strategy,
                effective_strategy=effective_primary,
                fallback_used=False,
                fallback_reason=None,
                command_executed=argv,
                bytes_transferred=0,
                duration_ms=0.0,
                throughput_mbps=0.0,
                dry_run=True,
            )

        dst.parent.mkdir(parents=True, exist_ok=True)
        self._check_disk_space(dst.parent, source_bytes, dst)

        start_ns = time.perf_counter_ns()
        fallback_used = False
        fallback_reason: str | None = None
        final_strategy = effective_primary
        executed_argv = argv

        if effective_primary == TransferStrategy.BUILTIN:
            try:
                self._run_builtin(src, dst, action)
            except Exception as err:
                self._cleanup_partial(dst)
                if self._is_enospc_error(exc=err):
                    raise TransferDiskFullError(
                        f"No space left on device during builtin {action.value} to '{dst}': {err}"
                    ) from err
                raise TransferExecutionError(
                    f"Builtin {action.value} failed from '{src}' to '{dst}': {err}"
                ) from err
        else:
            assert argv is not None
            is_timeout = False
            try:
                res = subprocess.run(
                    argv,
                    shell=False,
                    capture_output=True,
                    text=True,
                    timeout=active_cfg.timeout_seconds,
                )
                # Retry cp -r if --reflink=auto is unsupported by host cp binary
                if (
                    res.returncode != 0
                    and effective_primary == TransferStrategy.NATIVE
                    and action == TransferAction.COPY
                    and "--reflink=auto" in argv
                    and self._is_unsupported_reflink_error(res.stderr)
                ):
                    self._cleanup_partial(dst)
                    retry_argv = ["cp", "-r", str(src), str(dst)]
                    executed_argv = retry_argv
                    res = subprocess.run(
                        retry_argv,
                        shell=False,
                        capture_output=True,
                        text=True,
                        timeout=active_cfg.timeout_seconds,
                    )

                if res.returncode != 0:
                    err_detail = (res.stderr or res.stdout or "").strip()
                    if self._is_enospc_error(stderr=err_detail):
                        self._cleanup_partial(dst)
                        raise TransferDiskFullError(
                            f"No space left on device during {effective_primary.value} "
                            f"{action.value} to '{dst}': {err_detail}"
                        )
                    raise TransferExecutionError(
                        f"External {effective_primary.value} {action.value} command {executed_argv} "
                        f"exited with code {res.returncode}: {err_detail}"
                    )

                # For custom move commands: verify destination integrity and clean up remaining source
                if effective_primary == TransferStrategy.CUSTOM and action == TransferAction.MOVE:
                    if not dst.exists():
                        raise TransferExecutionError(
                            f"Custom move command exited 0 but destination '{dst}' does not exist"
                        )
                    dst_bytes = compute_path_size(dst)
                    if dst_bytes != source_bytes:
                        self._cleanup_partial(dst)
                        raise TransferExecutionError(
                            f"Custom move destination verification failed: size mismatch for '{dst}' "
                            f"(expected={source_bytes}, actual={dst_bytes})"
                        )
                    if src.exists() and src.resolve() != dst.resolve():
                        if src.is_dir() and not src.is_symlink():
                            shutil.rmtree(src)
                        else:
                            src.unlink()

            except TransferDiskFullError:
                raise
            except subprocess.TimeoutExpired as exc:
                is_timeout = True
                self._cleanup_partial(dst)
                fallback_reason = (
                    f"Command {executed_argv} timed out after {active_cfg.timeout_seconds}s"
                )
                if not active_cfg.fallback_enabled:
                    raise TransferTimeoutError(fallback_reason) from exc
            except FileNotFoundError as exc:
                self._cleanup_partial(dst)
                fallback_reason = f"Transfer binary not found for command {executed_argv}: {exc}"
                if not active_cfg.fallback_enabled:
                    raise TransferExecutionError(fallback_reason) from exc
            except Exception as exc:
                self._cleanup_partial(dst)
                if self._is_enospc_error(exc=exc):
                    raise TransferDiskFullError(
                        f"No space left on device during {effective_primary.value} {action.value}: {exc}"
                    ) from exc
                fallback_reason = str(exc)
                if not active_cfg.fallback_enabled:
                    if isinstance(exc, TransferExecutionError):
                        raise
                    raise TransferExecutionError(fallback_reason) from exc

            if fallback_reason is not None:
                logger.warning(
                    "Transfer via %s strategy failed (%s); cleaning up partial target and falling back to builtin shutil",
                    effective_primary.value,
                    fallback_reason,
                )
                self._check_disk_space(dst.parent, source_bytes, dst)
                try:
                    self._run_builtin(src, dst, action)
                    fallback_used = True
                    final_strategy = TransferStrategy.BUILTIN
                except Exception as fb_err:
                    self._cleanup_partial(dst)
                    if self._is_enospc_error(exc=fb_err):
                        raise TransferDiskFullError(
                            f"No space left on device during builtin fallback to '{dst}': {fb_err}"
                        ) from fb_err
                    if is_timeout:
                        raise TransferTimeoutError(
                            f"{fallback_reason}; builtin fallback also failed: {fb_err}"
                        ) from fb_err
                    raise TransferExecutionError(
                        f"{fallback_reason}; builtin fallback also failed: {fb_err}"
                    ) from fb_err

        elapsed_ms = max(0.001, (time.perf_counter_ns() - start_ns) / 1_000_000.0)
        mb_transferred = source_bytes / (1024.0 * 1024.0)
        throughput_mbps = mb_transferred / (elapsed_ms / 1000.0) if elapsed_ms > 0 else 0.0

        outcome = TransferOutcome(
            src=src,
            dst=dst,
            action=action,
            configured_strategy=active_cfg.strategy,
            effective_strategy=final_strategy,
            fallback_used=fallback_used,
            fallback_reason=fallback_reason,
            command_executed=executed_argv,
            bytes_transferred=source_bytes,
            duration_ms=elapsed_ms,
            throughput_mbps=throughput_mbps,
            dry_run=False,
        )
        self._summary.record(outcome)

        logger.info(
            "Completed %s transfer: %s -> %s (strategy=%s, fallback=%s, bytes=%d, duration_ms=%.2f, throughput_mbps=%.2f)",
            action.value,
            src.name,
            dst,
            final_strategy.value,
            fallback_used,
            source_bytes,
            elapsed_ms,
            throughput_mbps,
        )
        return outcome
