import logging

from media_cron.logging.base import SensitiveDataSanitizerProtocol
from media_cron.logging.sanitizer import SensitiveDataFilter


def test_sensitive_data_filter_implements_protocol():
    sanitizer = SensitiveDataFilter()
    assert isinstance(sanitizer, SensitiveDataSanitizerProtocol)


def test_sanitize_message_masks_secrets():
    sanitizer = SensitiveDataFilter()
    raw = "Connecting to http://admin:MySecretPass123@192.168.1.50:8080 with token=abcde12345"
    sanitized = sanitizer.sanitize_message(raw)
    assert "MySecretPass123" not in sanitized
    assert "abcde12345" not in sanitized
    assert "***REDACTED***" in sanitized


def test_filter_redacts_record_in_place():
    sanitizer = SensitiveDataFilter()
    record = logging.LogRecord(
        name="media_cron.auth",
        level=logging.INFO,
        pathname="auth.py",
        lineno=12,
        msg="API password=%s supplied",
        args=("SecretPassword999",),
        exc_info=None,
    )
    res = sanitizer.filter(record)
    assert res is True
    # formatted message must not contain secret
    formatted = record.getMessage()
    assert "SecretPassword999" not in formatted
    assert "***REDACTED***" in formatted
