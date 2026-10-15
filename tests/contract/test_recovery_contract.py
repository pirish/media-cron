import inspect

from media_cron.recovery.models import RecoverySummary
from media_cron.recovery.protocols import TransferVerifierProtocol


def test_transfer_verifier_protocol_conformance():
    """Verify that TransferVerifier conforms to TransferVerifierProtocol runtime contract."""
    from media_cron.recovery.verifier import TransferVerifier

    verifier = TransferVerifier()
    assert isinstance(verifier, TransferVerifierProtocol)

    # Check method signatures
    compute_sig = inspect.signature(verifier.compute_sha256)
    assert "file_path" in compute_sig.parameters
    assert "chunk_size" in compute_sig.parameters

    verify_sig = inspect.signature(verifier.verify_item)
    assert "source_path" in verify_sig.parameters
    assert "target_path" in verify_sig.parameters

    purge_sig = inspect.signature(verifier.purge_item)
    assert "target_path" in purge_sig.parameters
    assert "allowed_parent_roots" in purge_sig.parameters
    assert "dry_run" in purge_sig.parameters

    # Check summary property
    assert isinstance(verifier.summary, RecoverySummary)
