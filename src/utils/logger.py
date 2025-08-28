"""Настройка структурированного логирования."""

import logging
import sys
from typing import Any

import structlog

from ..config import settings


def configure_logging() -> None:
    """Настройка структурированных логов."""

    # Настройка structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="ISO", utc=True),
            structlog.processors.CallsiteParameterAdder(
                parameters=[structlog.processors.CallsiteParameter.FUNC_NAME]
            ),
            structlog.processors.JSONRenderer() if settings.LOG_FORMAT == "json"
            else structlog.dev.ConsoleRenderer()
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(settings.LOG_LEVEL)
        ),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Настройка стандартного logging
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL),
        format="%(message)s" if settings.LOG_FORMAT == "json" else
               "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )

    # Уменьшение verbose логов от внешних библиотек
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("gspread").setLevel(logging.INFO)
    logging.getLogger("google.auth").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.BoundLogger:
    """Получение логгера с контекстом."""
    return structlog.get_logger(name)


def log_function_call(
    logger: structlog.BoundLogger,
    func_name: str,
    args: tuple = (),
    kwargs: dict[str, Any] = None,
    result: Any = None,
    error: Exception = None
) -> None:
    """Логирование вызова функции."""
    kwargs = kwargs or {}

    log_data = {
        "function": func_name,
        "args_count": len(args),
        "kwargs_keys": list(kwargs.keys()) if kwargs else []
    }

    if error:
        logger.error(
            f"Function {func_name} failed",
            error=str(error),
            error_type=type(error).__name__,
            **log_data
        )
    else:
        logger.debug(
            f"Function {func_name} completed",
            result_type=type(result).__name__ if result is not None else None,
            **log_data
        )
