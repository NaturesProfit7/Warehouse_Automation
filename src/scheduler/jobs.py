"""Задачи планировщика для автоматических операций."""

from datetime import date, datetime, timedelta
from typing import Any

from ..core.calculations import get_stock_calculator
from ..core.models import ReplenishmentRecommendation, UrgencyLevel
from ..integrations.keycrm import get_keycrm_client
from ..integrations.sheets import get_sheets_client
from ..services.report_service import get_report_service
from ..services.stock_service import get_stock_service
from ..utils.logger import get_logger

logger = get_logger(__name__)


class ScheduledJobs:
    """Класс для управления запланированными задачами."""

    def __init__(self):
        self.stock_service = get_stock_service()
        self.report_service = get_report_service()
        self.stock_calculator = get_stock_calculator()
        self.sheets_client = get_sheets_client()

        logger.info("Scheduled jobs initialized")

    async def daily_stock_calculation(self):
        """
        Ежедневный расчет остатков и генерация рекомендаций.
        Выполняется каждый день в 20:00 по Europe/Kyiv.
        """

        job_id = f"daily_calc_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        try:
            logger.info("Starting daily stock calculation", job_id=job_id)

            # 1. Получаем текущие данные
            current_stocks = await self.stock_service.get_all_current_stock()
            master_blanks = self.sheets_client.get_master_blanks()

            logger.info(
                "Data loaded for daily calculation",
                job_id=job_id,
                stocks_count=len(current_stocks),
                master_blanks_count=len(master_blanks)
            )

            # 2. Рассчитываем рекомендации по пополнению
            recommendations = self.stock_calculator.calculate_replenishment_needs(
                current_stocks, master_blanks
            )

            # 3. Обновляем отчет пополнения в Sheets
            await self._update_replenishment_report(recommendations)

            # 4. Рассчитываем метрики склада
            metrics = self.stock_calculator.calculate_stock_metrics(current_stocks, master_blanks)

            # 5. Обновляем аналитический дашборд
            await self._update_analytics_dashboard(metrics)

            # 6. Отправляем ежедневные уведомления
            await self._send_daily_notifications(recommendations)

            # 7. Логируем результаты
            items_need_order = [r for r in recommendations if r.need_order]
            critical_items = [r for r in recommendations if r.urgency == UrgencyLevel.CRITICAL]

            logger.info(
                "Daily stock calculation completed",
                job_id=job_id,
                total_recommendations=len(recommendations),
                items_need_order=len(items_need_order),
                critical_items=len(critical_items)
            )

        except Exception as e:
            logger.error(
                "Daily stock calculation failed",
                job_id=job_id,
                error=str(e),
                error_type=type(e).__name__
            )

            # Отправляем уведомление об ошибке
            await self._send_error_notification(
                "Daily Stock Calculation Failed",
                str(e),
                job_id
            )

    async def daily_data_sync(self):
        """
        Ежедневная сверка данных с KeyCRM.
        Выполняется каждый день в 02:00 по Europe/Kyiv.
        """

        job_id = f"daily_sync_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        try:
            logger.info("Starting daily data sync", job_id=job_id)

            # Проверяем заказы за последние 7 дней
            start_date = date.today() - timedelta(days=7)

            keycrm_client = await get_keycrm_client()
            confirmed_orders = await keycrm_client.get_confirmed_orders_since(start_date)

            logger.info(
                "KeyCRM orders retrieved for sync",
                job_id=job_id,
                orders_count=len(confirmed_orders),
                date_range=f"{start_date} to {date.today()}"
            )

            # Обработка заказов
            processed_count = 0
            skipped_count = 0
            error_count = 0

            for order in confirmed_orders:
                try:
                    # Обработка каждого заказа
                    movements = await self.stock_service.process_order_movement(order)

                    if movements:
                        processed_count += 1
                    else:
                        skipped_count += 1

                except Exception as order_error:
                    error_count += 1
                    logger.warning(
                        "Error processing order during sync",
                        job_id=job_id,
                        order_id=order.id,
                        error=str(order_error)
                    )

            # Отправляем отчет о синхронизации
            await self._send_sync_report(job_id, processed_count, skipped_count, error_count)

            logger.info(
                "Daily data sync completed",
                job_id=job_id,
                processed=processed_count,
                skipped=skipped_count,
                errors=error_count
            )

        except Exception as e:
            logger.error(
                "Daily data sync failed",
                job_id=job_id,
                error=str(e),
                error_type=type(e).__name__
            )

            await self._send_error_notification(
                "Daily Data Sync Failed",
                str(e),
                job_id
            )

    async def hourly_unmapped_items_check(self):
        """
        Проверка unmapped позиций каждый час.
        """

        job_id = f"unmapped_check_{datetime.now().strftime('%H%M%S')}"

        try:
            logger.debug("Starting hourly unmapped items check", job_id=job_id)

            # Получаем unmapped items за последний час
            # TODO: Реализовать метод в sheets_client для получения recent unmapped items
            # unmapped_items = await self.sheets_client.get_recent_unmapped_items(hours=1)

            # Пока используем заглушку
            unmapped_count = 0  # len(unmapped_items)

            if unmapped_count > 0:
                await self._send_unmapped_items_notification(unmapped_count)
                logger.info("Unmapped items notification sent", count=unmapped_count)

        except Exception as e:
            logger.error("Hourly unmapped check failed", job_id=job_id, error=str(e))

    async def weekly_analytics_report(self):
        """
        Еженедельный аналитический отчет.
        Выполняется каждый понедельник в 09:00.
        """

        job_id = f"weekly_analytics_{datetime.now().strftime('%Y%m%d')}"

        try:
            logger.info("Starting weekly analytics report", job_id=job_id)

            # Генерируем расширенный отчет по движениям за неделю
            movements_report = await self.report_service.generate_movements_report(days_back=7)

            # Генерируем полный отчет по складу
            full_report = await self.report_service.generate_full_report()

            # Отправляем аналитический отчет
            await self._send_weekly_analytics(movements_report, full_report)

            logger.info("Weekly analytics report completed", job_id=job_id)

        except Exception as e:
            logger.error("Weekly analytics report failed", job_id=job_id, error=str(e))

    async def cleanup_old_data(self):
        """
        Очистка старых данных (выполняется еженедельно в 01:00 по воскресеньям).
        """

        job_id = f"cleanup_{datetime.now().strftime('%Y%m%d')}"

        try:
            logger.info("Starting data cleanup", job_id=job_id)

            # Очистка старых движений (старше 6 месяцев)
            cutoff_date = datetime.now() - timedelta(days=180)

            # TODO: Реализовать методы очистки в sheets_client
            # cleaned_movements = await self.sheets_client.cleanup_old_movements(cutoff_date)
            # cleaned_audit_logs = await self.sheets_client.cleanup_old_audit_logs(cutoff_date)

            cleaned_movements = 0  # Заглушка
            cleaned_audit_logs = 0  # Заглушка

            logger.info(
                "Data cleanup completed",
                job_id=job_id,
                movements_cleaned=cleaned_movements,
                audit_logs_cleaned=cleaned_audit_logs,
                cutoff_date=cutoff_date.date()
            )

        except Exception as e:
            logger.error("Data cleanup failed", job_id=job_id, error=str(e))

    async def check_stock_levels(self):
        """
        Комбинированная проверка остатков: критичные (красные) и низкие (желтые).
        Выполняется 3 раза в день: 10:00, 15:00, 21:00.
        """

        job_id = f"stock_check_{datetime.now().strftime('%H%M%S')}"

        try:
            logger.info("Starting stock levels check", job_id=job_id)

            # Получаем текущие данные
            current_stocks = await self.stock_service.get_all_current_stock()
            master_blanks = self.sheets_client.get_master_blanks()

            if not current_stocks or not master_blanks:
                logger.warning("No stock data available for check", job_id=job_id)
                return

            # Анализируем остатки
            critical_items = []  # Красные: < MIN_STOCK * 0.5
            low_items = []       # Желтые: < MIN_STOCK но >= MIN_STOCK * 0.5
            normal_count = 0

            for stock in current_stocks:
                # Находим соответствующую заготовку в справочнике
                blank = next((b for b in master_blanks if b['blank_sku'] == stock.blank_sku), None)
                if not blank or not blank.get('active', True):
                    continue

                min_stock = blank.get('MIN_STOCK', 100)
                on_hand = stock.on_hand

                if on_hand < min_stock * 0.5:
                    # Критичные остатки
                    critical_items.append({
                        'sku': stock.blank_sku,
                        'on_hand': on_hand,
                        'min_stock': min_stock
                    })
                elif on_hand < min_stock:
                    # Низкие остатки
                    low_items.append({
                        'sku': stock.blank_sku,
                        'on_hand': on_hand,
                        'min_stock': min_stock
                    })
                else:
                    normal_count += 1

            # Отправляем уведомление только если есть проблемы
            if critical_items or low_items:
                await self._send_combined_stock_alert(critical_items, low_items, normal_count)
                logger.info(
                    "Stock alert sent",
                    job_id=job_id,
                    critical_count=len(critical_items),
                    low_count=len(low_items),
                    normal_count=normal_count
                )
            else:
                logger.info("All stock levels are normal", job_id=job_id, total_skus=normal_count)

        except Exception as e:
            logger.error(
                "Stock levels check failed",
                job_id=job_id,
                error=str(e),
                error_type=type(e).__name__
            )

            # Отправляем уведомление об ошибке
            await self._send_error_notification(
                "Stock Levels Check Failed",
                str(e),
                job_id
            )

    async def _update_replenishment_report(self, recommendations: list[ReplenishmentRecommendation]):
        """Обновление отчета пополнения в Google Sheets."""

        try:
            self.sheets_client.update_replenishment_report(recommendations)
            logger.debug("Replenishment report updated", count=len(recommendations))
        except Exception as e:
            logger.error("Failed to update replenishment report", error=str(e))
            raise

    async def _update_analytics_dashboard(self, metrics: dict[str, Any]):
        """Обновление аналитического дашборда."""

        try:
            # TODO: Реализовать обновление Analytics_Dashboard листа
            logger.debug("Analytics dashboard updated", metrics_count=len(metrics))
        except Exception as e:
            logger.error("Failed to update analytics dashboard", error=str(e))

    async def _send_daily_notifications(self, recommendations: list[ReplenishmentRecommendation]):
        """Отправка ежедневных уведомлений в Telegram."""

        try:
            # Генерируем краткий отчет
            report_data = {
                "report_type": "short",
                "generated_at": datetime.now(),
                "total_skus": len(recommendations),
                "summary": {
                    "critical_count": len([r for r in recommendations if r.urgency == UrgencyLevel.CRITICAL]),
                    "high_priority_count": len([r for r in recommendations if r.urgency == UrgencyLevel.HIGH]),
                    "medium_priority_count": len([r for r in recommendations if r.urgency == UrgencyLevel.MEDIUM]),
                    "sufficient_count": len([r for r in recommendations if r.urgency == UrgencyLevel.LOW])
                },
                "critical_items": [
                    {
                        "blank_sku": r.blank_sku,
                        "on_hand": r.on_hand,
                        "min_level": r.min_level,
                        "recommended_qty": r.recommended_qty,
                        "urgency": r.urgency.value
                    }
                    for r in recommendations if r.urgency == UrgencyLevel.CRITICAL
                ][:5],
                "high_priority_items": [
                    {
                        "blank_sku": r.blank_sku,
                        "on_hand": r.on_hand,
                        "min_level": r.min_level,
                        "recommended_qty": r.recommended_qty
                    }
                    for r in recommendations if r.urgency == UrgencyLevel.HIGH
                ][:5]
            }

            # Форматируем для Telegram
            message = self.report_service.format_report_for_telegram(report_data)

            # TODO: Отправка через Telegram API
            logger.info("Daily notification prepared", message_length=len(message))

        except Exception as e:
            logger.error("Failed to send daily notifications", error=str(e))

    async def _send_sync_report(self, job_id: str, processed: int, skipped: int, errors: int):
        """Отправка отчета о синхронизации."""

        message = (
            f"🔄 <b>Звіт синхронізації</b>\n\n"
            f"📊 Оброблено: {processed} замовлень\n"
            f"⏩ Пропущено: {skipped} замовлень\n"
            f"❌ Помилок: {errors}\n"
            f"🕐 Час: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )

        # TODO: Отправка через Telegram API
        logger.info("Sync report prepared", processed=processed, skipped=skipped, errors=errors)

    async def _send_unmapped_items_notification(self, count: int):
        """Уведомление о незамапленных позициях."""

        message = (
            f"⚠️ <b>Позиції без маппінгу</b>\n\n"
            f"Знайдено {count} нових позицій без правил маппінгу.\n"
            f"Додайте правила в лист Mapping для автоматичної обробки."
        )

        # TODO: Отправка через Telegram API
        logger.info("Unmapped items notification prepared", count=count)

    async def _send_weekly_analytics(self, movements_report: dict, full_report: dict):
        """Отправка еженедельной аналитики."""

        message = (
            f"📊 <b>Тижневий аналітичний звіт</b>\n\n"
            f"📈 Рухи за тиждень: {movements_report['total_movements']}\n"
            f"📦 Всього позицій: {full_report['metrics']['total_skus']}\n"
            f"⚠️ Потребують уваги: {full_report['metrics']['skus_below_min']}\n\n"
            f"Детальна інформація доступна через команди /report"
        )

        # TODO: Отправка через Telegram API
        logger.info("Weekly analytics prepared")

    async def _send_error_notification(self, title: str, error: str, job_id: str):
        """Отправка уведомления об ошибке."""

        message = (
            f"🚨 <b>Помилка системи</b>\n\n"
            f"<b>Операція:</b> {title}\n"
            f"<b>Job ID:</b> {job_id}\n"
            f"<b>Помилка:</b> {error[:200]}...\n"
            f"<b>Час:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
            f"Перевірте логи системи для деталей."
        )

        # TODO: Отправка админам через Telegram API
        logger.error("Error notification prepared", title=title, job_id=job_id)

    async def _send_combined_stock_alert(self, critical_items: list, low_items: list, normal_count: int):
        """Отправка комбинированного уведомления о критических и низких остатках."""

        try:
            current_time = datetime.now().strftime('%H:%M')
            message_parts = [f"📦 <b>ПЕРЕВІРКА ЗАЛИШКІВ • {current_time}</b>\n"]

            # Критичные остатки (красные)
            if critical_items:
                message_parts.append("🔴 <b>Критично (потребують негайних дій):</b>")
                for item in critical_items[:10]:  # Максимум 10 позиций
                    sku_display = self._format_sku_for_message(item['sku'])
                    message_parts.append(f"• {sku_display}: {item['on_hand']}/{item['min_stock']} шт")
                
                if len(critical_items) > 10:
                    message_parts.append(f"... та ще {len(critical_items) - 10} позицій")
                message_parts.append("")

            # Низкие остатки (желтые)
            if low_items:
                message_parts.append("🟡 <b>Низькі залишки (потрібно замовити):</b>")
                for item in low_items[:10]:  # Максимум 10 позиций
                    sku_display = self._format_sku_for_message(item['sku'])
                    message_parts.append(f"• {sku_display}: {item['on_hand']}/{item['min_stock']} шт")
                
                if len(low_items) > 10:
                    message_parts.append(f"... та ще {len(low_items) - 10} позицій")
                message_parts.append("")

            # Статистика
            if normal_count > 0:
                message_parts.append(f"✅ <b>В нормі:</b> {normal_count} позицій")

            # Итоговая информация
            total_problems = len(critical_items) + len(low_items)
            if total_problems > 0:
                message_parts.append(f"\n📊 <b>Загалом проблемних позицій:</b> {total_problems}")
                message_parts.append("💡 Використовуйте /analytics для детального аналізу")

            message = "\n".join(message_parts)

            # TODO: Отправка через Telegram API
            logger.info(
                "Combined stock alert prepared",
                message_length=len(message),
                critical_items=len(critical_items),
                low_items=len(low_items),
                normal_count=normal_count
            )

        except Exception as e:
            logger.error("Failed to prepare combined stock alert", error=str(e))

    def _format_sku_for_message(self, sku: str) -> str:
        """Форматирование SKU для красивого отображения в сообщении."""

        parts = sku.split('-')
        if len(parts) != 4:
            return sku

        _, sku_type, size, color = parts

        # Маппинг типов
        type_mapping = {
            "BONE": "🦴 Кістка",
            "RING": "🟢 Бублик", 
            "ROUND": "⚪ Круглий",
            "HEART": "❤️ Серце",
            "FLOWER": "🌸 Квітка",
            "CLOUD": "☁️ Хмарка"
        }

        # Маппинг цветов
        color_mapping = {
            "GLD": "🟡",
            "SIL": "⚪"
        }

        type_display = type_mapping.get(sku_type, sku_type)
        color_display = color_mapping.get(color, color)

        return f"{type_display} {size}мм {color_display}"


# Глобальный экземпляр задач
_scheduled_jobs: ScheduledJobs = None


def get_scheduled_jobs() -> ScheduledJobs:
    """Получение экземпляра запланированных задач."""
    global _scheduled_jobs

    if _scheduled_jobs is None:
        _scheduled_jobs = ScheduledJobs()

    return _scheduled_jobs
