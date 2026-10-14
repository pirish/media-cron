import logging

from media_cron.logging.sanitizer import SensitiveDataFilter


def test_sanitize_key_value_patterns():
    filter_ = SensitiveDataFilter()
    cases = [
        ("password=MyPassword123!", "password=***REDACTED***"),
        ("token: 'abc123secret'", "token: '***REDACTED***'"),
        ('api_key="secret-key-456"', 'api_key="***REDACTED***"'),
        ("secret=99999", "secret=***REDACTED***"),
        ("auth=BearerTokenHere", "auth=***REDACTED***"),
        ("pass = plaintext", "pass = ***REDACTED***"),
    ]
    for raw, expected in cases:
        sanitized = filter_.sanitize_message(raw)
        assert sanitized == expected, f"Failed for {raw}: got {sanitized}"


def test_sanitize_url_basic_auth():
    filter_ = SensitiveDataFilter()
    raw = "Connecting to http://admin:superSecret123@qbittorrent.local:8080/api/v2"
    sanitized = filter_.sanitize_message(raw)
    assert "superSecret123" not in sanitized
    assert "http://admin:***REDACTED***@qbittorrent.local:8080/api/v2" in sanitized


def test_sanitize_authorization_header():
    filter_ = SensitiveDataFilter()
    raw = "Header Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    sanitized = filter_.sanitize_message(raw)
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in sanitized
    assert "Bearer ***REDACTED***" in sanitized


def test_filter_scrubs_dict_context():
    filter_ = SensitiveDataFilter()
    record = logging.LogRecord(
        name="media_cron.config",
        level=logging.DEBUG,
        pathname="config.py",
        lineno=10,
        msg="Client options: %s",
        args=({"username": "admin", "password": "supersecretpassword"},),
        exc_info=None,
    )
    filter_.filter(record)
    formatted = record.getMessage()
    assert "supersecretpassword" not in formatted
    assert "***REDACTED***" in formatted
