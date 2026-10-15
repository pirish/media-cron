"""Fast failure recovery and transfer resumption subsystem."""

from media_cron.recovery.models import (
    FileIntegrityRecord,
    RecoverySummary,
    VerificationResult,
    VerificationStatus,
)
from media_cron.recovery.protocols import TransferVerifierProtocol

__all__ = [
    "FileIntegrityRecord",
    "RecoverySummary",
    "TransferVerifier",
    "TransferVerifierProtocol",
    "VerificationResult",
    "VerificationStatus",
]


def __getattr__(name: str):
    if name == "TransferVerifier":
        from media_cron.recovery.verifier import TransferVerifier

        return TransferVerifier
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
