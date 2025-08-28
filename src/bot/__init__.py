"""Telegram бот для управления заготовками."""

import asyncio
import logging
from typing import Any, Dict

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from ..config import settings
from ..utils.logger import get_logger
from .handlers import router
from .middleware import AuthMiddleware, LoggingMiddleware, StateMiddleware

logger = get_logger(__name__)


def create_bot() -> tuple[Bot, Dispatcher]:
    """Создание и настройка бота."""

    # Создаем бота с новым API aiogram 3.7+
    bot = Bot(
        token=settings.TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="HTML")
    )

    # Создаем диспетчер с хранилищем состояний
    dp = Dispatcher(storage=MemoryStorage())

    # Регистрируем middleware
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())

    dp.message.middleware(LoggingMiddleware())
    dp.callback_query.middleware(LoggingMiddleware())

    dp.message.middleware(StateMiddleware())
    dp.callback_query.middleware(StateMiddleware())

    # Регистрируем роутер с обработчиками
    dp.include_router(router)

    logger.info("Telegram bot created and configured")

    return bot, dp


async def start_polling():
    """Запуск бота в режиме polling."""

    try:
        bot, dp = create_bot()

        # Устанавливаем команды бота
        from aiogram.types import BotCommand

        commands = [
            BotCommand(command="start", description="Головне меню"),
            BotCommand(command="receipt", description="Додати поставку"),
            BotCommand(command="report", description="Звіт по залишкам"),
            BotCommand(command="health", description="Статус системи"),
            BotCommand(command="help", description="Довідка"),
            BotCommand(command="cancel", description="Скасувати операцію")
        ]

        await bot.set_my_commands(commands)
        logger.info("Bot commands set")

        # Уведомляем о запуске
        await _notify_startup(bot)

        # Запускаем polling
        logger.info("Starting bot polling...")
        await dp.start_polling(bot)

    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise
    finally:
        if 'bot' in locals():
            await bot.session.close()


async def _notify_startup(bot: Bot) -> None:
    """Уведомление о запуске бота."""

    try:
        admin_ids = settings.TELEGRAM_ADMIN_USERS
        if not admin_ids:
            return

        startup_message = (
            "🤖 <b>Бот запущено</b>\n\n"
            "✅ Система контролю заготовок готова до роботи\n"
            "⏰ Час запуску: {}\n\n"
            "Для початку роботи натисніть /start"
        )

        from datetime import datetime
        current_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        message_text = startup_message.format(current_time)

        for admin_id in admin_ids:
            try:
                await bot.send_message(admin_id, message_text, parse_mode="HTML")
            except Exception as e:
                logger.warning(f"Failed to notify admin {admin_id} about startup: {e}")

    except Exception as e:
        logger.error(f"Failed to send startup notification: {e}")


async def stop_bot() -> None:
    """Корректное завершение работы бота."""

    logger.info("Stopping Telegram bot...")

    try:
        # Здесь можно добавить cleanup логику
        pass
    except Exception as e:
        logger.error(f"Error during bot shutdown: {e}")


if __name__ == "__main__":
    """Запуск бота как отдельного процесса."""

    logging.basicConfig(level=logging.INFO)

    try:
        asyncio.run(start_polling())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        raise
