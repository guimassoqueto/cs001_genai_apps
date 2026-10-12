import logging
import re
import time
import uuid
from contextvars import ContextVar
from logging.config import dictConfig

from flask import Flask, g, request

logger = logging.getLogger("genai_app.access")

# A ContextVar (not flask.g) so the id also reaches the threads that call the models.
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

_INCOMING_ID = re.compile(r"[A-Za-z0-9._-]{1,128}")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def configure_logging(level: str) -> None:
    """Send every log line to stderr, tagged with the current request id."""
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {"request_id": {"()": RequestIdFilter}},
            "formatters": {
                "default": {"format": "%(asctime)s %(levelname)-7s [%(request_id)s] %(name)s: %(message)s"},
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stderr",
                    "formatter": "default",
                    "filters": ["request_id"],
                },
            },
            "root": {"level": level, "handlers": ["console"]},
            # Third-party HTTP clients log every request at INFO.
            "loggers": {name: {"level": "WARNING"} for name in ("httpx", "httpcore", "anthropic")},
        }
    )


def get_request_id() -> str:
    return request_id_var.get()


def init_request_logging(app: Flask) -> None:
    """Give every request an id (reusing a valid incoming X-Request-ID), echo it back and log the request."""

    @app.before_request
    def start_request() -> None:
        incoming = request.headers.get("X-Request-ID", "")
        request_id = incoming if _INCOMING_ID.fullmatch(incoming) else uuid.uuid4().hex
        g.request_id_token = request_id_var.set(request_id)
        g.request_started = time.perf_counter()

    @app.after_request
    def finish_request(response):
        response.headers["X-Request-ID"] = request_id_var.get()
        elapsed_ms = (time.perf_counter() - g.get("request_started", time.perf_counter())) * 1000
        level = logging.DEBUG if request.endpoint == "static" else logging.INFO
        logger.log(level, "%s %s -> %s in %.0fms", request.method, request.path, response.status_code, elapsed_ms)
        return response

    @app.teardown_request
    def reset_request_id(_exc: BaseException | None) -> None:
        token = g.pop("request_id_token", None)
        if token is not None:
            request_id_var.reset(token)
