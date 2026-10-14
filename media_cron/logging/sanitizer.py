import logging
import re
from typing import Any

# Regex patterns matching key-value pairs, URL basic auth, and Authorization headers
PATTERNS = [
    # Key-value: password=xyz, token: 'xyz', "api_key": "xyz", pass = plaintext
    re.compile(
        r"""(?i)(['"]?)\b(password|token|secret|api[_-]?key|auth|pass)\b\1(\s*[:=]\s*)(['"]?)([^'"\s,;&]+)\4"""
    ),
    # URL basic auth: http://user:pass@host
    re.compile(r"(https?://[^:\s]+:)([^@\s]+)(@)"),
    # Authorization header: Bearer xyz / Basic xyz
    re.compile(r"(?i)\b(Bearer|Basic)\s+([A-Za-z0-9\-._~+/]+=*)"),
]


class SensitiveDataFilter(logging.Filter):
    """Filter that intercepts log records and scrubs sensitive credentials."""

    def sanitize_message(self, message: str) -> str:
        """Applies regex redaction patterns to any input string."""
        if not isinstance(message, str):
            message = str(message)

        # 1. Key-value pairs
        sanitized = PATTERNS[0].sub(r"\1\2\1\3\4***REDACTED***\4", message)

        # 2. URL basic auth
        sanitized = PATTERNS[1].sub(r"\1***REDACTED***\3", sanitized)

        # 3. Auth headers
        sanitized = PATTERNS[2].sub(r"\1 ***REDACTED***", sanitized)

        return sanitized

    def _sanitize_arg(self, arg: Any) -> Any:
        if isinstance(arg, str):
            return self.sanitize_message(arg)
        elif isinstance(arg, dict):
            new_dict = {}
            for k, v in arg.items():
                if any(
                    pat in str(k).lower()
                    for pat in ["password", "token", "secret", "key", "pass", "auth"]
                ):
                    new_dict[k] = "***REDACTED***"
                else:
                    new_dict[k] = self._sanitize_arg(v)
            return new_dict
        elif isinstance(arg, list | tuple):
            cleaned = [self._sanitize_arg(x) for x in arg]
            return type(arg)(cleaned)
        return arg

    def filter(self, record: logging.LogRecord) -> bool:
        """Sanitizes record message and arguments in-place."""
        try:
            if record.args:
                if isinstance(record.args, dict):
                    record.args = self._sanitize_arg(record.args)
                elif isinstance(record.args, tuple):
                    record.args = tuple(self._sanitize_arg(a) for a in record.args)
                elif isinstance(record.args, list):
                    record.args = [self._sanitize_arg(a) for a in record.args]
                # Merge message with args first to prevent specifier collisions
                merged = record.getMessage()
                record.msg = self.sanitize_message(merged)
                record.args = ()
            elif isinstance(record.msg, str):
                record.msg = self.sanitize_message(record.msg)
        except Exception:
            if isinstance(record.msg, str):
                record.msg = self.sanitize_message(record.msg)
            if record.args:
                if isinstance(record.args, dict):
                    record.args = self._sanitize_arg(record.args)
                elif isinstance(record.args, tuple):
                    record.args = tuple(self._sanitize_arg(a) for a in record.args)
                elif isinstance(record.args, list):
                    record.args = [self._sanitize_arg(a) for a in record.args]

        return True
