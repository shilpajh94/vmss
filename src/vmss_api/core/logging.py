import logging
import sys

import structlog


def configure_logging(debug: bool, log_level: str = "INFO") -> None:
    level = logging.getLevelNamesMapping().get(log_level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.ConsoleRenderer() if debug else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
    )


logger = structlog.get_logger("vmss_api")


def current_request_id() -> str:
    """The request id bound by `core/middleware.py::RequestIdMiddleware`, or
    "" outside a request — passed to Celery tasks so they can rebind it
    (logging-observability.md §1)."""
    return str(structlog.contextvars.get_contextvars().get("request_id", ""))
