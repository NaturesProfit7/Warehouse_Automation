"""Запуск и управление планировщиком задач."""

import asyncio
import signal
import sys
from datetime import datetime

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from ..config import settings
from ..utils.logger import configure_logging, get_logger
from .jobs import get_scheduled_jobs

# Настройка логирования
configure_logging()
logger = get_logger(__name__)


class SchedulerRunner:
    """Менеджер планировщика задач."""

    def __init__(self):
        self.scheduler: AsyncIOScheduler | None = None
        self.scheduled_jobs = get_scheduled_jobs()
        self.is_running = False

        logger.info("Scheduler runner initialized")

    def create_scheduler(self) -> AsyncIOScheduler:
        """Создание и настройка планировщика."""

        scheduler = AsyncIOScheduler(
            timezone=settings.TIMEZONE,
            # Настройки хранилища задач
            job_defaults={
                'coalesce': True,  # Объединять пропущенные выполнения
                'max_instances': 1,  # Не более одного экземпляра задачи одновременно
                'misfire_grace_time': 60  # Допустимая задержка в секундах
            }
        )

        # Подписываемся на события
        scheduler.add_listener(self._job_executed, EVENT_JOB_EXECUTED)
        scheduler.add_listener(self._job_error, EVENT_JOB_ERROR)

        return scheduler

    def add_jobs(self):
        """Добавление всех запланированных задач."""

        try:
            # Ежедневный расчет остатков (21:01)
            self.scheduler.add_job(
                func=self.scheduled_jobs.daily_stock_calculation,
                trigger=CronTrigger(
                    hour=21,
                    minute=1,
                    timezone=settings.TIMEZONE
                ),
                id='daily_stock_calculation',
                name='Daily Stock Calculation',
                replace_existing=True,
                max_instances=1
            )

            # Ежедневная сверка данных (02:00)
            self.scheduler.add_job(
                func=self.scheduled_jobs.daily_data_sync,
                trigger=CronTrigger(
                    hour=2,
                    minute=0,
                    timezone=settings.TIMEZONE
                ),
                id='daily_data_sync',
                name='Daily Data Sync',
                replace_existing=True,
                max_instances=1
            )

            # Проверка unmapped позиций каждый час
            self.scheduler.add_job(
                func=self.scheduled_jobs.hourly_unmapped_items_check,
                trigger=CronTrigger(
                    minute=0,  # Каждый час в начале часа
                    timezone=settings.TIMEZONE
                ),
                id='hourly_unmapped_check',
                name='Hourly Unmapped Items Check',
                replace_existing=True,
                max_instances=1
            )

            # Комбинированные уведомления о остатках (10:00)
            self.scheduler.add_job(
                func=self.scheduled_jobs.check_stock_levels,
                trigger=CronTrigger(
                    hour=10,
                    minute=0,
                    timezone=settings.TIMEZONE
                ),
                id='stock_check_morning',
                name='Stock Check - Morning',
                replace_existing=True,
                max_instances=1
            )

            # Комбинированные уведомления о остатках (15:00)
            self.scheduler.add_job(
                func=self.scheduled_jobs.check_stock_levels,
                trigger=CronTrigger(
                    hour=15,
                    minute=0,
                    timezone=settings.TIMEZONE
                ),
                id='stock_check_afternoon',
                name='Stock Check - Afternoon',
                replace_existing=True,
                max_instances=1
            )

            # Комбинированные уведомления о остатках (21:00)
            self.scheduler.add_job(
                func=self.scheduled_jobs.check_stock_levels,
                trigger=CronTrigger(
                    hour=21,
                    minute=0,
                    timezone=settings.TIMEZONE
                ),
                id='stock_check_evening',
                name='Stock Check - Evening',
                replace_existing=True,
                max_instances=1
            )

            # Еженедельный аналитический отчет (понедельник 10:30)
            self.scheduler.add_job(
                func=self.scheduled_jobs.weekly_analytics_report,
                trigger=CronTrigger(
                    day_of_week='mon',
                    hour=10,
                    minute=30,
                    timezone=settings.TIMEZONE
                ),
                id='weekly_analytics',
                name='Weekly Analytics Report',
                replace_existing=True,
                max_instances=1
            )

            # Очистка старых данных (воскресенье 01:00)
            self.scheduler.add_job(
                func=self.scheduled_jobs.cleanup_old_data,
                trigger=CronTrigger(
                    day_of_week='sun',
                    hour=1,
                    minute=0,
                    timezone=settings.TIMEZONE
                ),
                id='cleanup_old_data',
                name='Cleanup Old Data',
                replace_existing=True,
                max_instances=1
            )

            # В DEBUG режиме добавляем тестовые задачи
            if settings.DEBUG:
                # Тестовая задача каждые 5 минут
                self.scheduler.add_job(
                    func=self._test_job,
                    trigger=IntervalTrigger(minutes=5),
                    id='test_job',
                    name='Test Job (Debug)',
                    replace_existing=True
                )

            logger.info("All scheduled jobs added successfully")

            # Выводим информацию о задачах
            self._log_scheduled_jobs()

        except Exception as e:
            logger.error("Failed to add scheduled jobs", error=str(e))
            raise

    async def start(self):
        """Запуск планировщика."""

        try:
            if self.is_running:
                logger.warning("Scheduler is already running")
                return

            logger.info("Starting scheduler runner")

            # Создаем планировщик
            self.scheduler = self.create_scheduler()

            # Добавляем задачи
            self.add_jobs()

            # Запускаем планировщик
            self.scheduler.start()
            self.is_running = True

            logger.info(
                "Scheduler started successfully",
                timezone=settings.TIMEZONE,
                jobs_count=len(self.scheduler.get_jobs())
            )

            # Отправляем уведомление о запуске
            await self._notify_scheduler_start()

        except Exception as e:
            logger.error("Failed to start scheduler", error=str(e))
            raise

    async def stop(self):
        """Остановка планировщика."""

        if not self.is_running or not self.scheduler:
            logger.warning("Scheduler is not running")
            return

        try:
            logger.info("Stopping scheduler...")

            # Ожидаем завершения текущих задач
            self.scheduler.shutdown(wait=True)

            self.is_running = False
            self.scheduler = None

            logger.info("Scheduler stopped successfully")

        except Exception as e:
            logger.error("Error stopping scheduler", error=str(e))
            raise

    async def run_forever(self):
        """Запуск планировщика в режиме постоянной работы."""

        try:
            # Запускаем планировщик
            await self.start()

            # Настраиваем обработку сигналов
            def signal_handler(signum, frame):
                logger.info(f"Received signal {signum}, shutting down...")
                asyncio.create_task(self.stop())
                sys.exit(0)

            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)

            logger.info("Scheduler is running. Press Ctrl+C to stop.")

            # Основной цикл
            while self.is_running:
                await asyncio.sleep(1)

        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        except Exception as e:
            logger.error("Error in scheduler main loop", error=str(e))
            raise
        finally:
            await self.stop()

    def get_job_status(self) -> dict:
        """Получение статуса всех задач."""

        if not self.scheduler:
            return {"status": "not_running", "jobs": []}

        jobs_info = []
        for job in self.scheduler.get_jobs():
            jobs_info.append({
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger)
            })

        return {
            "status": "running" if self.is_running else "stopped",
            "jobs_count": len(jobs_info),
            "jobs": jobs_info,
            "timezone": settings.TIMEZONE
        }

    async def run_job_now(self, job_id: str):
        """Немедленный запуск задачи."""

        if not self.scheduler:
            raise RuntimeError("Scheduler is not running")

        try:
            job = self.scheduler.get_job(job_id)
            if not job:
                raise ValueError(f"Job {job_id} not found")

            logger.info(f"Running job {job_id} manually")

            # Запускаем задачу
            if job_id == 'daily_stock_calculation':
                await self.scheduled_jobs.daily_stock_calculation()
            elif job_id == 'daily_data_sync':
                await self.scheduled_jobs.daily_data_sync()
            elif job_id == 'hourly_unmapped_check':
                await self.scheduled_jobs.hourly_unmapped_items_check()
            elif job_id == 'weekly_analytics':
                await self.scheduled_jobs.weekly_analytics_report()
            elif job_id == 'cleanup_old_data':
                await self.scheduled_jobs.cleanup_old_data()
            elif job_id in ['stock_check_morning', 'stock_check_afternoon', 'stock_check_evening']:
                await self.scheduled_jobs.check_stock_levels()
            else:
                raise ValueError(f"Unknown job: {job_id}")

            logger.info(f"Job {job_id} completed manually")

        except Exception as e:
            logger.error(f"Error running job {job_id} manually", error=str(e))
            raise

    def _job_executed(self, event):
        """Обработчик успешного выполнения задачи."""

        logger.info(
            "Job executed successfully",
            job_id=event.job_id,
            job_name=getattr(event, 'job_name', 'unknown'),
            scheduled_run_time=event.scheduled_run_time,
            executed_time=datetime.now()
        )

    def _job_error(self, event):
        """Обработчик ошибки выполнения задачи."""

        logger.error(
            "Job execution failed",
            job_id=event.job_id,
            job_name=getattr(event, 'job_name', 'unknown'),
            exception=str(event.exception),
            scheduled_run_time=event.scheduled_run_time,
            traceback=event.traceback
        )

    def _log_scheduled_jobs(self):
        """Логирование информации о запланированных задачах."""

        if not self.scheduler:
            return

        logger.info("Scheduled jobs overview:")

        for job in self.scheduler.get_jobs():
            next_run = job.next_run_time.strftime('%d.%m.%Y %H:%M:%S') if job.next_run_time else "Not scheduled"
            logger.info(
                f"  {job.id}: {job.name}",
                trigger=str(job.trigger),
                next_run=next_run
            )

    async def _test_job(self):
        """Тестовая задача для отладки."""

        logger.info("Test job executed", timestamp=datetime.now())

    async def _notify_scheduler_start(self):
        """Уведомление о запуске планировщика."""

        try:
            message = (
                f"⏰ <b>Планировщик запущено</b>\n\n"
                f"✅ Автоматичні завдання активні\n"
                f"🕐 Часовий пояс: {settings.TIMEZONE}\n"
                f"📦 Перевірка залишків: 10:00, 15:00, 21:00\n"
                f"📊 Щоденний розрахунок: 21:01\n"
                f"🔄 Синхронізація даних: {settings.DAILY_SYNC_TIME}\n"
                f"📈 Тижнева аналітика: Пн 10:30\n\n"
                f"Система готова до роботи."
            )

            # TODO: Отправка через Telegram API админам
            logger.info("Scheduler start notification prepared")

        except Exception as e:
            logger.error("Failed to send scheduler start notification", error=str(e))


# Глобальный экземпляр runner
_scheduler_runner: SchedulerRunner | None = None


def get_scheduler_runner() -> SchedulerRunner:
    """Получение глобального экземпляра scheduler runner."""
    global _scheduler_runner

    if _scheduler_runner is None:
        _scheduler_runner = SchedulerRunner()

    return _scheduler_runner


async def main():
    """Главная функция для запуска планировщика."""

    logger.info("Starting Timosh Blanks Scheduler")

    try:
        runner = get_scheduler_runner()
        await runner.run_forever()
    except Exception as e:
        logger.error("Scheduler startup failed", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    """Точка входа для запуска планировщика как отдельного процесса."""

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
    except Exception as e:
        logger.error("Scheduler crashed", error=str(e))
        sys.exit(1)
