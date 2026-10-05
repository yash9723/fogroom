"""Structured-ish logging. Never log passwords, tokens or Authorization headers."""

import logging
import sys

from app.core.config import settings

_SENSITIVE = ("password", "token", "authorization", "secret")


class RedactingFilter(logging.Filter):
    """Defensive filter: masks values of sensitive keys passed via `extra`."""

    def filter(self, record: logging.LogRecord) -> bool:
        for key in list(record.__dict__):
            if any(s in key.lower() for s in _SENSITIVE):
                setattr(record, key, "***")
        return True


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-7s %(name)s | %(message)s", "%Y-%m-%dT%H:%M:%S")
    )
    handler.addFilter(RedactingFilter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log_level.upper())
    # uvicorn's access log includes query strings only; we never put tokens in URLs.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
