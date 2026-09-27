import logging
import sys

import structlog


def setup_logging(log_level: str = "INFO", service: str | None = None) -> None:
    """
    Sets up logging configuration for the application.

    Args:
        log_level (str): The logging level to be set. Default is "INFO".
        service (str | None): Service name added to every log line, e.g. "gateway".
    """
    # Configure the root logger
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level.upper(),
    )

    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]
    if service:
        processors.append(_add_service(service))
    processors += [
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ]

    # Configure structlog to use the standard library's logging
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def _add_service(service: str) -> structlog.types.Processor:
    def processor(
        _logger: structlog.types.WrappedLogger, _method: str, event_dict: structlog.types.EventDict
    ) -> structlog.types.EventDict:
        event_dict.setdefault("service", service)
        return event_dict

    return processor


logger = structlog.get_logger()
