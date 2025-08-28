"""Планировщик фоновых задач системы."""

import asyncio
from datetime import datetime, time, timedelta
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import pytz

from ..config import settings
from ..utils.logger import get_logger
from .notification_service import get_notification_service
from .stock_service import get_stock_service

logger = get_logger(__name__)


class SchedulerService:
    """Сервис планирования фоновых задач."""
    
    def __init__(self):
        # Используем таймзону Киева
        self.timezone = pytz.timezone('Europe/Kyiv')
        self.scheduler = AsyncIOScheduler(timezone=self.timezone)
        self.notification_service = get_notification_service()
        self.stock_service = get_stock_service()
        self._running = False
        
        logger.info("Scheduler service initialized", timezone=str(self.timezone))
    
    async def start(self) -> None:
        """Запуск планировщика с настройкой всех задач."""
        if self._running:
            logger.warning("Scheduler is already running")
            return
        
        try:
            logger.info("Starting scheduler...")
            
            # Настраиваем задачи
            await self._setup_jobs()
            
            # Запускаем планировщик
            self.scheduler.start()
            self._running = True
            
            logger.info("✅ Scheduler started successfully")
            
        except Exception as e:
            logger.error("Failed to start scheduler", error=str(e))
            raise
    
    async def stop(self) -> None:
        """Остановка планировщика."""
        if not self._running:
            return
        
        try:
            logger.info("Stopping scheduler...")
            self.scheduler.shutdown(wait=True)
            self._running = False
            logger.info("✅ Scheduler stopped")
            
        except Exception as e:
            logger.error("Failed to stop scheduler", error=str(e))
    
    async def _setup_jobs(self) -> None:
        """Настройка всех периодических задач."""
        
        # 1. Проверка критических остатков каждый час
        self.scheduler.add_job(
            func=self._check_critical_stock_job,
            trigger=IntervalTrigger(hours=1),
            id="check_critical_stock",
            name="Проверка критических остатков",
            replace_existing=True,
            misfire_grace_time=300,  # 5 минут на выполнение после пропуска
            coalesce=True  # Объединяем пропущенные запуски
        )
        
        # 2. Ежедневная сводка в 10:30
        self.scheduler.add_job(
            func=self._daily_summary_job,
            trigger=CronTrigger(hour=10, minute=30),
            id="daily_summary",
            name="Ежедневная сводка",
            replace_existing=True,
            misfire_grace_time=3600  # 1 час на выполнение после пропуска
        )
        
        # 3. Обновление статистики использования каждые 6 часов
        self.scheduler.add_job(
            func=self._update_usage_stats_job,
            trigger=IntervalTrigger(hours=6),
            id="update_usage_stats",
            name="Обновление статистики использования",
            replace_existing=True,
            misfire_grace_time=1800  # 30 минут на выполнение
        )
        
        # 4. Проверка статуса системы каждые 15 минут
        self.scheduler.add_job(
            func=self._system_health_check_job,
            trigger=IntervalTrigger(minutes=15),
            id="system_health_check",
            name="Проверка состояния системы",
            replace_existing=True,
            misfire_grace_time=300
        )
        
        logger.info("All scheduled jobs configured successfully")
    
    async def _check_critical_stock_job(self) -> None:
        """Задача проверки критических остатков."""
        try:
            logger.debug("Running critical stock check job")
            
            # Проверяем критические остатки
            alert = await self.notification_service.check_critical_stock()
            
            if alert:
                # Отправляем уведомление в Telegram
                success = await self.notification_service.send_telegram_alert(alert)
                
                if success:
                    logger.info(
                        "Critical stock alert sent successfully", 
                        critical_count=len(alert.critical_items),
                        high_priority_count=len(alert.high_priority_items)
                    )
                else:
                    logger.error("Failed to send critical stock alert")
            else:
                logger.debug("No critical stock alerts needed")
                
        except Exception as e:
            logger.error("Critical stock check job failed", error=str(e))
    
    async def _daily_summary_job(self) -> None:
        """Задача генерации ежедневной сводки."""
        try:
            logger.info("Running daily summary job")
            
            # Проверяем включена ли ежедневная сводка
            if not self.notification_service.config.daily_summary_enabled:
                logger.debug("Daily summary is disabled, skipping")
                return
            
            # Генерируем сводку
            summary = await self.notification_service.generate_daily_summary()
            
            if summary:
                # Отправляем всем админам
                admin_ids = settings.TELEGRAM_ADMIN_USERS
                success_count = 0
                
                for admin_id in admin_ids:
                    try:
                        await self.notification_service._send_telegram_message(admin_id, summary)
                        success_count += 1
                    except Exception as e:
                        logger.error("Failed to send daily summary to admin", 
                                   admin_id=admin_id, error=str(e))
                
                logger.info(
                    "Daily summary sent", 
                    total_admins=len(admin_ids),
                    successful_sends=success_count
                )
            else:
                logger.warning("Failed to generate daily summary")
                
        except Exception as e:
            logger.error("Daily summary job failed", error=str(e))
    
    async def _update_usage_stats_job(self) -> None:
        """Задача обновления статистики использования."""
        try:
            logger.debug("Running usage stats update job")
            
            # Обновляем статистику использования для всех SKU
            updated_count = await self.stock_service.update_usage_statistics()
            
            logger.info(
                "Usage statistics updated",
                updated_skus=updated_count
            )
            
        except Exception as e:
            logger.error("Usage stats update job failed", error=str(e))
    
    async def _system_health_check_job(self) -> None:
        """Задача проверки состояния системы."""
        try:
            logger.debug("Running system health check job")
            
            # Проверяем доступность Google Sheets
            sheets_healthy = await self._check_sheets_health()
            
            # Проверяем доступность Telegram Bot API
            telegram_healthy = await self._check_telegram_health()
            
            # Проверяем состояние базовых сервисов
            services_healthy = await self._check_services_health()
            
            overall_healthy = all([sheets_healthy, telegram_healthy, services_healthy])
            
            logger.info(
                "System health check completed",
                overall_healthy=overall_healthy,
                sheets_healthy=sheets_healthy,
                telegram_healthy=telegram_healthy,
                services_healthy=services_healthy
            )
            
            # Если есть критические проблемы, отправляем уведомление
            if not overall_healthy:
                await self._send_health_alert(sheets_healthy, telegram_healthy, services_healthy)
                
        except Exception as e:
            logger.error("System health check job failed", error=str(e))
    
    async def _check_sheets_health(self) -> bool:
        """Проверка доступности Google Sheets."""
        try:
            from ..integrations.sheets import get_sheets_client
            sheets_client = get_sheets_client()
            
            # Пытаемся получить небольшой объем данных
            master_blanks = sheets_client.get_master_blanks()
            return len(master_blanks) > 0
            
        except Exception as e:
            logger.warning("Google Sheets health check failed", error=str(e))
            return False
    
    async def _check_telegram_health(self) -> bool:
        """Проверка доступности Telegram Bot API."""
        try:
            import httpx
            
            if not settings.TELEGRAM_BOT_TOKEN:
                return False
            
            url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/getMe"
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=10.0)
                return response.status_code == 200
                
        except Exception as e:
            logger.warning("Telegram health check failed", error=str(e))
            return False
    
    async def _check_services_health(self) -> bool:
        """Проверка состояния основных сервисов."""
        try:
            # Проверяем что сервисы инициализируются без ошибок
            _ = get_notification_service()
            _ = await self.stock_service.get_all_current_stock()
            return True
            
        except Exception as e:
            logger.warning("Services health check failed", error=str(e))
            return False
    
    async def _send_health_alert(
        self, 
        sheets_healthy: bool, 
        telegram_healthy: bool, 
        services_healthy: bool
    ) -> None:
        """Отправка уведомления о проблемах в системе."""
        try:
            problems = []
            
            if not sheets_healthy:
                problems.append("❌ Google Sheets недоступен")
            if not telegram_healthy:
                problems.append("❌ Telegram Bot API недоступен")
            if not services_healthy:
                problems.append("❌ Внутренние сервисы не работают")
            
            if not problems:
                return
            
            message = f"""🚨 <b>ПРОБЛЕМЫ В СИСТЕМЕ</b>

⚠️ <b>Обнаружены проблемы:</b>
{chr(10).join(problems)}

🕒 Время: {datetime.now(self.timezone).strftime('%d.%m.%Y %H:%M')}

💡 Проверьте логи системы для получения подробностей."""
            
            # Отправляем только если Telegram доступен
            if telegram_healthy and settings.TELEGRAM_ADMIN_USERS:
                for admin_id in settings.TELEGRAM_ADMIN_USERS:
                    try:
                        await self.notification_service._send_telegram_message(admin_id, message)
                    except Exception as e:
                        logger.error("Failed to send health alert", admin_id=admin_id, error=str(e))
            
        except Exception as e:
            logger.error("Failed to send health alert", error=str(e))
    
    def get_job_status(self) -> dict:
        """Получение статуса всех задач."""
        if not self._running:
            return {"status": "stopped", "jobs": []}
        
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger)
            })
        
        return {
            "status": "running",
            "jobs": jobs,
            "timezone": str(self.timezone)
        }
    
    async def trigger_job_manually(self, job_id: str) -> bool:
        """Ручной запуск задачи."""
        try:
            job = self.scheduler.get_job(job_id)
            if not job:
                logger.warning(f"Job {job_id} not found")
                return False
            
            logger.info(f"Manually triggering job: {job_id}")
            
            # Запускаем задачу
            job.modify(next_run_time=datetime.now(self.timezone))
            
            return True
            
        except Exception as e:
            logger.error("Failed to trigger job manually", job_id=job_id, error=str(e))
            return False


# Глобальный экземпляр планировщика
_scheduler_service: Optional[SchedulerService] = None


def get_scheduler_service() -> SchedulerService:
    """Получение глобального экземпляра планировщика."""
    global _scheduler_service
    
    if _scheduler_service is None:
        _scheduler_service = SchedulerService()
    
    return _scheduler_service