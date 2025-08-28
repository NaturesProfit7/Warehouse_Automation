"""Middleware для Telegram бота."""

from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, User

from ..config import settings
from ..utils.logger import get_logger

logger = get_logger(__name__)


class AuthMiddleware(BaseMiddleware):
    """Middleware для авторизации пользователей по whitelist."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any]
    ) -> Any:
        """Проверка авторизации пользователя."""

        user: User | None = data.get("event_from_user")
        if not user:
            # Пропускаем события без пользователя
            return await handler(event, data)

        user_id = user.id
        username = user.username or "unknown"

        # Проверка в whitelist
        if user_id not in settings.TELEGRAM_ALLOWED_USERS:
            # Неавторизованный пользователь
            logger.warning(
                "Unauthorized access attempt",
                user_id=user_id,
                username=username,
                full_name=user.full_name
            )

            # Отправляем сообщение о запрете доступа
            if isinstance(event, (Message, CallbackQuery)):
                await event.answer("⛔ Доступ заборонено\nЗверніться до адміністратора")

            # Уведомляем администраторов
            await self._notify_admins_about_unauthorized_access(user, event, data)

            return  # Прерываем обработку

        # Авторизованный пользователь
        logger.info(
            "Authorized user action",
            user_id=user_id,
            username=username,
            is_admin=user_id in settings.TELEGRAM_ADMIN_USERS
        )

        # Добавляем информацию об авторизации в данные
        data["is_admin"] = user_id in settings.TELEGRAM_ADMIN_USERS
        data["user_info"] = {
            "id": user_id,
            "username": username,
            "full_name": user.full_name
        }

        return await handler(event, data)

    async def _notify_admins_about_unauthorized_access(
        self,
        user: User,
        event: TelegramObject,
        data: dict[str, Any]
    ) -> None:
        """Уведомление администраторов о попытке несанкционированного доступа."""

        try:

            bot = data.get("bot") if isinstance(event, TelegramObject) else None
            if not bot:
                return

            admin_ids = settings.TELEGRAM_ADMIN_USERS
            if not admin_ids:
                return

            message_text = (
                f"🚨 Попытка несанкционированного доступа\n\n"
                f"👤 Пользователь: {user.full_name}\n"
                f"🆔 ID: {user.id}\n"
                f"📝 Username: @{user.username or 'не указан'}\n"
                f"⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
            )

            for admin_id in admin_ids:
                try:
                    await bot.send_message(admin_id, message_text)
                except Exception as e:
                    logger.warning(f"Failed to notify admin {admin_id}: {e}")

        except Exception as e:
            logger.error(f"Failed to notify admins about unauthorized access: {e}")


class LoggingMiddleware(BaseMiddleware):
    """Middleware для логирования действий пользователей."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any]
    ) -> Any:
        """Логирование действий пользователей."""

        user_info = data.get("user_info", {})
        user_id = user_info.get("id", "unknown")

        # Определяем тип события
        event_type = type(event).__name__

        # Логируем начало обработки
        logger.debug(
            f"Processing {event_type}",
            user_id=user_id,
            event_type=event_type
        )

        try:
            # Выполняем обработчик
            result = await handler(event, data)

            # Логируем успешное выполнение
            logger.info(
                f"Successfully processed {event_type}",
                user_id=user_id,
                event_type=event_type
            )

            return result

        except Exception as e:
            # Логируем ошибку
            logger.error(
                f"Error processing {event_type}",
                user_id=user_id,
                event_type=event_type,
                error=str(e),
                error_type=type(e).__name__
            )
            raise


class StateMiddleware(BaseMiddleware):
    """Middleware для управления состояниями диалогов."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any]
    ) -> Any:
        """Добавление утилит для работы с состояниями."""

        from aiogram.fsm.context import FSMContext

        state: FSMContext = data.get("state")

        if state:
            # Добавляем удобные методы для работы с состоянием
            data["clear_state"] = state.clear
            data["set_state"] = state.set_state
            data["get_state"] = state.get_state
            data["get_data"] = state.get_data
            data["update_data"] = state.update_data

        return await handler(event, data)
