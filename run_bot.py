#!/usr/bin/env python3
"""Скрипт запуска Telegram бота для управления заготовками."""

import asyncio
import logging
import signal
import sys

from src.bot import start_polling, stop_bot
from src.utils.logger import get_logger

logger = get_logger(__name__)


def setup_logging():
    """Настройка логирования для бота."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Отключаем слишком подробное логирование aiogram
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)


async def graceful_shutdown(sig_name: str):
    """Корректное завершение работы при получении сигнала."""
    logger.info(f"Received {sig_name}, shutting down gracefully...")
    
    try:
        await stop_bot()
        logger.info("Bot stopped successfully")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
    finally:
        sys.exit(0)


def signal_handler(sig_num, frame):
    """Обработчик системных сигналов."""
    sig_name = signal.Signals(sig_num).name
    logger.info(f"Received signal {sig_name}")
    
    # Создаем задачу для корректного завершения
    asyncio.create_task(graceful_shutdown(sig_name))


async def main():
    """Главная функция запуска бота."""
    
    logger.info("🤖 Starting Timosh Blanks Telegram Bot...")
    
    try:
        # Настраиваем обработчики сигналов для корректного завершения
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Запускаем бота
        await start_polling()
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (Ctrl+C)")
        await graceful_shutdown("KeyboardInterrupt")
        
    except Exception as e:
        logger.error(f"Bot crashed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    setup_logging()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot terminated")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)