"""Retry декораторы для обработки временных ошибок."""

import asyncio
import functools
import logging
import random
from typing import Callable, Type, Union, Tuple, Any

from ..core.exceptions import RetryableError
from ..config import settings

logger = logging.getLogger(__name__)


def exponential_backoff(
    max_retries: int = None,
    base_delay: float = None, 
    max_delay: float = 60,
    backoff_factor: float = 2,
    jitter: bool = True,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    Декоратор для повторных попыток с экспоненциальным backoff.
    
    Args:
        max_retries: Максимум попыток (по умолчанию из settings)
        base_delay: Начальная задержка в секундах (по умолчанию из settings) 
        max_delay: Максимальная задержка в секундах
        backoff_factor: Коэффициент увеличения задержки
        jitter: Добавлять случайность к задержке
        retryable_exceptions: Исключения для повтора
    """
    if max_retries is None:
        max_retries = settings.MAX_RETRIES
    if base_delay is None:
        base_delay = settings.RETRY_DELAY_SECONDS
        
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        logger.error(
                            f"Final retry attempt failed for {func.__name__}: {e}",
                            extra={
                                "function": func.__name__,
                                "attempt": attempt + 1,
                                "max_retries": max_retries,
                                "error": str(e)
                            }
                        )
                        break
                    
                    delay = min(base_delay * (backoff_factor ** attempt), max_delay)
                    if jitter:
                        delay *= (0.5 + random.random() * 0.5)  # +/- 25% jitter
                    
                    logger.warning(
                        f"Retry {attempt + 1}/{max_retries} for {func.__name__} in {delay:.2f}s: {e}",
                        extra={
                            "function": func.__name__,
                            "attempt": attempt + 1,
                            "delay": delay,
                            "error": str(e)
                        }
                    )
                    
                    await asyncio.sleep(delay)
            
            raise last_exception
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        logger.error(
                            f"Final retry attempt failed for {func.__name__}: {e}",
                            extra={
                                "function": func.__name__,
                                "attempt": attempt + 1,
                                "max_retries": max_retries,
                                "error": str(e)
                            }
                        )
                        break
                    
                    delay = min(base_delay * (backoff_factor ** attempt), max_delay)
                    if jitter:
                        delay *= (0.5 + random.random() * 0.5)
                    
                    logger.warning(
                        f"Retry {attempt + 1}/{max_retries} for {func.__name__} in {delay:.2f}s: {e}",
                        extra={
                            "function": func.__name__,
                            "attempt": attempt + 1,
                            "delay": delay,
                            "error": str(e)
                        }
                    )
                    
                    import time
                    time.sleep(delay)
            
            raise last_exception
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
            
    return decorator


def google_sheets_retry(func: Callable) -> Callable:
    """Специализированный retry для Google Sheets API."""
    from gspread.exceptions import APIError
    
    return exponential_backoff(
        retryable_exceptions=(APIError, RetryableError, ConnectionError, TimeoutError)
    )(func)