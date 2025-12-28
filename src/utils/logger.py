"""Structured logging configuration using structlog."""

import logging
import sys
from typing import Literal

import structlog
from structlog.typing import Processor


def setup_logging(
    level: str = "INFO",
    format_type: Literal["json", "console"] = "console",
) -> None:
    """
    Configure structured logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        format_type: Output format - 'json' for production, 'console' for development
    """
    # Shared processors
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if format_type == "json":
        # Production: JSON output
        processors: list[Processor] = [
            *shared_processors,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Development: Pretty console output
        processors = [
            *shared_processors,
            structlog.dev.ConsoleRenderer(
                colors=True,
                exception_formatter=structlog.dev.rich_traceback,
            ),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Also configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, level.upper()),
        stream=sys.stdout,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """
    Get a logger instance.

    Args:
        name: Optional logger name (usually module name)

    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)


# Convenience function for masking sensitive data
def mask_sensitive(value: str, visible_chars: int = 4) -> str:
    """
    Mask sensitive data for logging.

    Args:
        value: The sensitive string to mask
        visible_chars: Number of characters to show at the end

    Returns:
        Masked string (e.g., "****word")
    """
    if len(value) <= visible_chars:
        return "*" * len(value)
    return "*" * (len(value) - visible_chars) + value[-visible_chars:]
