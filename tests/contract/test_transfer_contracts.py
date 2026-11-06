from pathlib import Path
from unittest.mock import patch

import pytest

from media_cron.config import MediaCronConfig
from media_cron.routing.models import SupportedMediaType
from media_cron.routing.resolver import RouteResolver
from media_cron.transfer.base import TransferExecutorProtocol
from media_cron.transfer.executor import FileTransferExecutor
from media_cron.transfer.models import TransferConfig, TransferStrategy


def test_executor_satisfies_transfer_executor_protocol() -> None:
    executor = FileTransferExecutor()
    assert isinstance(executor, TransferExecutorProtocol)
    assert executor.config.strategy == TransferStrategy.NATIVE


def test_shell_false_invariant_on_all_subprocess_invocations(tmp_path: Path) -> None:
    src = tmp_path / "Bad; echo PWNED & $(whoami).mkv"
    src.write_bytes(b"safe_bytes")
    dst = tmp_path / "out" / src.name

    executor = FileTransferExecutor(
        TransferConfig(
            strategy=TransferStrategy.CUSTOM,
            copy_command="cp -r {src} {dst}",
        )
    )

    observed_kwargs: list[dict] = []
    real_run = __import__("subprocess").run

    def spy_run(argv, **kwargs):
        observed_kwargs.append(kwargs)
        return real_run(argv, **kwargs)

    with patch("subprocess.run", side_effect=spy_run):
        executor.copy(src, dst)

    assert len(observed_kwargs) == 1
    assert observed_kwargs[0].get("shell") is False
    assert dst.exists()


def test_config_and_env_precedence_and_route_inheritance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
transfer:
  strategy: native
  fallback_enabled: true
  timeout_seconds: 1800

routes:
  movie:
    destination:
      path: /tmp/nas/movies
      mode: copy
      transfer:
        strategy: custom
        copy_command: "cp -r {src} {dst}"
""",
        encoding="utf-8",
    )

    cfg = MediaCronConfig.load(config_file)
    assert cfg.transfer.strategy == TransferStrategy.NATIVE
    assert cfg.transfer.fallback_enabled is True
    assert cfg.transfer.timeout_seconds == 1800.0

    resolver = RouteResolver()
    routes = resolver.resolve_all_routes(cfg)
    movie_route = routes[SupportedMediaType.MOVIES]
    assert movie_route.destination_endpoint.path == Path("/tmp/nas/movies")
    assert movie_route.destination_endpoint.transfer is not None
    assert movie_route.destination_endpoint.transfer.strategy == TransferStrategy.CUSTOM
    assert movie_route.destination_endpoint.transfer.copy_command == "cp -r {src} {dst}"
    # Inherited from global transfer block
    assert movie_route.destination_endpoint.transfer.timeout_seconds == 1800.0

    # Environment variable overrides global config
    monkeypatch.setenv("MEDIA_CRON_TRANSFER_STRATEGY", "builtin")
    monkeypatch.setenv("MEDIA_CRON_TRANSFER_FALLBACK_ENABLED", "false")
    monkeypatch.setenv("MEDIA_CRON_TRANSFER_TIMEOUT_SECONDS", "600")

    cfg_env = MediaCronConfig.load(config_file)
    assert cfg_env.transfer.strategy == TransferStrategy.BUILTIN
    assert cfg_env.transfer.fallback_enabled is False
    assert cfg_env.transfer.timeout_seconds == 600.0
