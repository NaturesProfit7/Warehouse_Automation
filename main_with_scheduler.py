#!/usr/bin/env python3
"""Главный модуль запуска системы с планировщиком."""

import asyncio
import logging
import signal
from typing import Optional
from datetime import datetime

from src.bot import create_bot
from src.services.scheduler_service import get_scheduler_service
from src.services.stock_service import get_stock_service
from src.utils.logger import get_logger

logger = get_logger(__name__)


class WarehouseApp:
    """Основное приложение системы управления складом."""
    
    def __init__(self):
        self.bot = None
        self.dp = None
        self.scheduler = None
        self.running = False
        self.start_time = datetime.now()
    
    def get_health_status(self) -> dict:
        """Получение статуса здоровья системы для мониторинга."""
        try:
            uptime_seconds = (datetime.now() - self.start_time).total_seconds()
            
            return {
                "status": "healthy" if self.running else "starting",
                "uptime_seconds": uptime_seconds,
                "timestamp": datetime.now().isoformat(),
                "components": {
                    "bot": "running" if self.bot else "stopped",
                    "scheduler": "running" if self.scheduler and self.scheduler._running else "stopped",
                    "dispatcher": "running" if self.dp else "stopped"
                }
            }
        except Exception as e:
            logger.error(f"Error getting health status: {e}")
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        
    async def start(self):
        """Запуск всех компонентов системы."""
        try:
            logger.info("🚀 Starting Warehouse Automation System...")
            
            # Создаем бота
            logger.info("Initializing Telegram bot...")
            self.bot, self.dp = create_bot()
            
            # Проверяем единственность экземпляра бота
            await self._ensure_single_bot_instance()
            
            # Устанавливаем команды
            await self._set_bot_commands()
            
            # Инициализируем планировщик
            logger.info("Initializing scheduler service...")
            self.scheduler = get_scheduler_service()
            await self.scheduler.start()
            
            # Инициализируем сервисы
            logger.info("Initializing core services...")
            stock_service = get_stock_service()
            logger.info("Stock service initialized")
            
            # Уведомляем о запуске
            await self._notify_startup()
            
            self.running = True
            logger.info("✅ All services started successfully!")
            
            # Запускаем polling с настройками для избежания конфликтов
            polling_task = asyncio.create_task(
                self.dp.start_polling(
                    self.bot,
                    drop_pending_updates=True,  # Сбрасываем старые обновления
                    timeout=30,  # Таймаут для long polling
                    allowed_updates=None  # Получаем все типы обновлений
                )
            )
            
            logger.info("📱 Bot polling started")
            
            # Ждем завершения
            await polling_task
            
        except Exception as e:
            logger.error(f"Failed to start application: {e}")
            await self.stop()
            raise
    
    async def stop(self):
        """Остановка всех компонентов системы."""
        if not self.running:
            return
            
        logger.info("🛑 Stopping Warehouse Automation System...")
        
        try:
            # Останавливаем планировщик
            if self.scheduler:
                await self.scheduler.stop()
                logger.info("Scheduler stopped")
            
            # Закрываем сессию бота
            if self.bot:
                await self.bot.session.close()
                logger.info("Bot session closed")
                
            self.running = False
            logger.info("✅ Application stopped gracefully")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
    
    async def _set_bot_commands(self):
        """Установка команд бота."""
        from aiogram.types import BotCommand
        
        commands = [
            BotCommand(command="start", description="Головне меню"),
            BotCommand(command="receipt", description="Додати поставку"),
            BotCommand(command="report", description="Звіт по залишкам"),
            BotCommand(command="health", description="Статус системи"),
            BotCommand(command="help", description="Довідка"),
            BotCommand(command="cancel", description="Скасувати операцію")
        ]
        
        await self.bot.set_my_commands(commands)
        logger.info("Bot commands configured")
    
    async def _ensure_single_bot_instance(self):
        """Проверка единственности экземпляра бота и очистка старых сессий."""
        try:
            # Пытаемся получить информацию о боте для проверки токена
            bot_info = await self.bot.get_me()
            logger.info(f"Bot verified: @{bot_info.username} (ID: {bot_info.id})")
            
            # Удаляем webhook если он был установлен (для polling)
            await self.bot.delete_webhook(drop_pending_updates=True)
            logger.info("Webhook removed, pending updates dropped")
            
            # Небольшая пауза для очистки старых соединений
            await asyncio.sleep(1)
            
        except Exception as e:
            logger.warning(f"Error ensuring single bot instance: {e}")
            # Продолжаем работу даже если проверка не удалась
    
    async def _notify_startup(self):
        """Уведомление администраторов о запуске."""
        from src.config import settings
        from datetime import datetime
        
        try:
            admin_ids = settings.TELEGRAM_ADMIN_USERS
            if not admin_ids:
                logger.warning("No admin user IDs configured for startup notification")
                return
            
            startup_message = f"""🚀 <b>Система запущена</b>

✅ Telegram бот активен
✅ Планировщик уведомлений запущен  
✅ Мониторинг системы работает
✅ Сервисы остатков готовы

🕒 Время запуска: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}

💡 Используйте /health для проверки состояния системы"""
            
            for admin_id in admin_ids:
                try:
                    await self.bot.send_message(admin_id, startup_message, parse_mode="HTML")
                    logger.debug(f"Startup notification sent to admin {admin_id}")
                except Exception as e:
                    logger.warning(f"Failed to notify admin {admin_id}: {e}")
                    
        except Exception as e:
            logger.error(f"Failed to send startup notifications: {e}")


# Глобальная переменная для доступа к приложению из health endpoint
warehouse_app_instance = None


async def simple_health_server():
    """Простой HTTP сервер для health checks."""
    from aiohttp import web
    
    async def health_check(request):
        """Endpoint для проверки здоровья."""
        if warehouse_app_instance:
            health_data = warehouse_app_instance.get_health_status()
            status = 200 if health_data.get("status") in ["healthy", "starting"] else 503
            return web.json_response(health_data, status=status)
        else:
            return web.json_response({
                "status": "error",
                "error": "Application not initialized",
                "timestamp": datetime.now().isoformat()
            }, status=503)
    
    # Создаем веб-приложение
    app = web.Application()
    app.router.add_get('/health', health_check)
    app.router.add_get('/', health_check)  # root тоже отвечает health
    
    # Запускаем сервер на порту 9001
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 9001)
    await site.start()
    
    logger.info("Health check server started on http://0.0.0.0:9001")
    return runner


async def main():
    """Основная функция запуска."""
    global warehouse_app_instance
    
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Запускаем health check сервер
    health_runner = await simple_health_server()
    
    # Создаем приложение
    app = WarehouseApp()
    warehouse_app_instance = app  # Сохраняем для health endpoint
    
    # Обработка сигналов для корректного завершения
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}, shutting down...")
        asyncio.create_task(app.stop())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Запускаем приложение
        await app.start()
        
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Application crashed: {e}")
        raise
    finally:
        await app.stop()
        # Останавливаем health сервер
        if health_runner:
            await health_runner.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        exit(1)