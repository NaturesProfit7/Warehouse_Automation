"""Утилиты аутентификации и авторизации для Telegram бота."""

from functools import wraps
from typing import Any, Callable

from aiogram.types import Message, CallbackQuery

from ..config import settings
from .logger import get_logger

logger = get_logger(__name__)


def admin_required(handler: Callable) -> Callable:
    """
    Декоратор для проверки прав администратора.
    
    Args:
        handler: Обработчик события
        
    Returns:
        Callable: Обернутый обработчик
    """
    
    @wraps(handler)
    async def wrapper(update: Message | CallbackQuery, *args, **kwargs):
        # Определяем пользователя
        if isinstance(update, Message):
            user_id = update.from_user.id
            user_name = update.from_user.full_name
        elif isinstance(update, CallbackQuery):
            user_id = update.from_user.id
            user_name = update.from_user.full_name
        else:
            logger.warning("Unknown update type", update_type=type(update))
            return
        
        # Проверяем права
        admin_ids = settings.TELEGRAM_ADMIN_USERS or []
        if user_id not in admin_ids:
            logger.warning(
                "Access denied - user is not admin",
                user_id=user_id,
                user_name=user_name
            )
            
            error_message = "❌ Недостатньо прав доступу"
            
            if isinstance(update, Message):
                await update.reply(error_message)
            elif isinstance(update, CallbackQuery):
                await update.answer(error_message, show_alert=True)
            
            return
        
        # Пользователь - админ, выполняем обработчик
        logger.debug(
            "Admin access granted",
            user_id=user_id,
            user_name=user_name
        )
        
        return await handler(update, *args, **kwargs)
    
    return wrapper


def get_user_info(update: Message | CallbackQuery) -> dict[str, Any]:
    """
    Извлечение информации о пользователе.
    
    Args:
        update: Обновление от Telegram
        
    Returns:
        Dict[str, Any]: Информация о пользователе
    """
    
    if isinstance(update, (Message, CallbackQuery)):
        user = update.from_user
        return {
            "id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "full_name": user.full_name,
            "language_code": user.language_code,
            "is_admin": user.id in (settings.TELEGRAM_ADMIN_USERS or [])
        }
    
    return {
        "id": None,
        "username": None,
        "first_name": None,
        "last_name": None,
        "full_name": "Unknown",
        "language_code": None,
        "is_admin": False
    }


def is_admin(user_id: int) -> bool:
    """
    Проверка является ли пользователь администратором.
    
    Args:
        user_id: ID пользователя
        
    Returns:
        bool: True если пользователь - админ
    """
    admin_ids = settings.TELEGRAM_ADMIN_USERS or []
    return user_id in admin_ids