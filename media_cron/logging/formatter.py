import datetime
import logging


class StandardTextFormatter(logging.Formatter):
    """
    Standard human-readable text formatter for terminal output.
    Outputs: YYYY-MM-DD HH:MM:SS [LEVEL] logger.name: message
    """

    def __init__(
        self,
        fmt: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt: str = "%Y-%m-%d %H:%M:%S",
    ) -> None:
        super().__init__(fmt=fmt, datefmt=datefmt)

    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()
        if self.usesTime():
            record.asctime = self.formatTime(record, self.datefmt)

        s = f"{record.asctime} [{record.levelname}] {record.name}: {record.message}"
        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
            if record.exc_text:
                if s[-1:] != "\n":
                    s = s + "\n"
                s = s + record.exc_text
        if record.stack_info:
            if s[-1:] != "\n":
                s = s + "\n"
            s = s + self.formatStack(record.stack_info)
        return s


class JsonLogFormatter(logging.Formatter):
    """
    Machine-readable JSON formatter producing single-line JSON records
    conforming strictly to contracts/json-log-schema.md.
    """

    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()

        dt = datetime.datetime.fromtimestamp(record.created, tz=datetime.UTC)
        iso_timestamp = dt.isoformat()

        context = getattr(record, "context", {})
        if not isinstance(context, dict):
            context = {"raw_context": str(context)}

        exception = None
        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
            exception = record.exc_text

        import json

        payload = {
            "timestamp": iso_timestamp,
            "level": record.levelname,
            "logger": record.name,
            "message": record.message,
            "context": context,
            "exception": exception,
        }

        return json.dumps(payload, default=str)
