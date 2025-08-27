"""Сервис генерации отчетов по остаткам и движениям."""

from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from ..core.calculations import get_stock_calculator
from ..core.models import UrgencyLevel
from ..integrations.sheets import get_sheets_client
from ..services.stock_service import get_stock_service
from ..utils.logger import get_logger

logger = get_logger(__name__)


class ReportType(str, Enum):
    """Типы отчетов."""
    SHORT = "short"
    FULL = "full"
    CRITICAL = "critical"
    MOVEMENTS = "movements"
    ANALYTICS = "analytics"


class ReportService:
    """Сервис для генерации отчетов."""

    def __init__(self):
        self.stock_service = get_stock_service()
        self.stock_calculator = get_stock_calculator()
        self.sheets_client = get_sheets_client()

        logger.info("Report service initialized")

    async def generate_short_report(self) -> dict[str, Any]:
        """
        Генерация краткого отчета по остаткам.
        
        Returns:
            Dict[str, Any]: Краткий отчет
        """

        try:
            logger.info("Generating short stock report")

            # Получаем данные
            current_stocks = await self.stock_service.get_all_current_stock()
            master_blanks = self.sheets_client.get_master_blanks()

            # Рассчитываем рекомендации
            recommendations = self.stock_calculator.calculate_replenishment_needs(
                current_stocks, master_blanks
            )

            # Группируем по приоритетам
            critical_items = [r for r in recommendations if r.urgency == UrgencyLevel.CRITICAL]
            high_items = [r for r in recommendations if r.urgency == UrgencyLevel.HIGH]
            medium_items = [r for r in recommendations if r.urgency == UrgencyLevel.MEDIUM]
            sufficient_items = [r for r in recommendations if r.urgency == UrgencyLevel.LOW]

            # Формируем отчет
            report = {
                "report_type": "short",
                "generated_at": datetime.now(),
                "total_skus": len(recommendations),
                "summary": {
                    "critical_count": len(critical_items),
                    "high_priority_count": len(high_items),
                    "medium_priority_count": len(medium_items),
                    "sufficient_count": len(sufficient_items)
                },
                "critical_items": [
                    {
                        "blank_sku": item.blank_sku,
                        "on_hand": item.on_hand,
                        "min_level": item.min_level,
                        "recommended_qty": item.recommended_qty,
                        "urgency": item.urgency.value
                    }
                    for item in critical_items[:5]  # Топ 5 критичных
                ],
                "high_priority_items": [
                    {
                        "blank_sku": item.blank_sku,
                        "on_hand": item.on_hand,
                        "min_level": item.min_level,
                        "recommended_qty": item.recommended_qty
                    }
                    for item in high_items[:5]  # Топ 5 приоритетных
                ]
            }

            logger.info(
                "Short report generated",
                total_items=len(recommendations),
                critical=len(critical_items),
                high_priority=len(high_items)
            )

            return report

        except Exception as e:
            logger.error("Failed to generate short report", error=str(e))
            raise

    async def generate_full_report(self) -> dict[str, Any]:
        """
        Генерация полного отчета по складу.
        
        Returns:
            Dict[str, Any]: Полный отчет
        """

        try:
            logger.info("Generating full stock report")

            # Получаем все данные
            current_stocks = await self.stock_service.get_all_current_stock()
            master_blanks = self.sheets_client.get_master_blanks()

            # Рассчитываем метрики и рекомендации
            metrics = self.stock_calculator.calculate_stock_metrics(current_stocks, master_blanks)
            recommendations = self.stock_calculator.calculate_replenishment_needs(
                current_stocks, master_blanks
            )

            # Группируем данные по типам заготовок
            stock_by_type = {}
            master_dict = {blank.blank_sku: blank for blank in master_blanks}

            for stock in current_stocks:
                master = master_dict.get(stock.blank_sku)
                if not master:
                    continue

                stock_type = master.type.value
                if stock_type not in stock_by_type:
                    stock_by_type[stock_type] = []

                # Находим рекомендацию для этого SKU
                recommendation = next((r for r in recommendations if r.blank_sku == stock.blank_sku), None)

                stock_info = {
                    "blank_sku": stock.blank_sku,
                    "name_ua": master.name_ua,
                    "size_mm": master.size_mm,
                    "color": master.color.value,
                    "on_hand": stock.on_hand,
                    "min_level": master.min_stock,
                    "par_level": master.par_stock,
                    "status": self._get_stock_status(stock.on_hand, master.min_stock),
                    "need_order": recommendation.need_order if recommendation else False,
                    "recommended_qty": recommendation.recommended_qty if recommendation else 0,
                    "last_receipt_date": stock.last_receipt_date,
                    "last_order_date": stock.last_order_date
                }

                stock_by_type[stock_type].append(stock_info)

            # Формируем полный отчет
            report = {
                "report_type": "full",
                "generated_at": datetime.now(),
                "metrics": metrics,
                "stock_by_type": stock_by_type,
                "recommendations_summary": {
                    "total_recommendations": len(recommendations),
                    "items_need_order": len([r for r in recommendations if r.need_order]),
                    "total_recommended_qty": sum(r.recommended_qty for r in recommendations),
                    "critical_items": len([r for r in recommendations if r.urgency == UrgencyLevel.CRITICAL])
                }
            }

            logger.info("Full report generated", total_types=len(stock_by_type))
            return report

        except Exception as e:
            logger.error("Failed to generate full report", error=str(e))
            raise

    async def generate_critical_items_report(self) -> dict[str, Any]:
        """
        Генерация отчета только по критичным позициям.
        
        Returns:
            Dict[str, Any]: Отчет по критичным позициям
        """

        try:
            logger.info("Generating critical items report")

            # Получаем данные
            current_stocks = await self.stock_service.get_all_current_stock()
            master_blanks = self.sheets_client.get_master_blanks()

            # Рассчитываем рекомендации
            recommendations = self.stock_calculator.calculate_replenishment_needs(
                current_stocks, master_blanks
            )

            # Фильтруем только критичные и требующие заказа
            critical_recommendations = [
                r for r in recommendations
                if r.urgency in [UrgencyLevel.CRITICAL, UrgencyLevel.HIGH] or r.need_order
            ]

            # Детальный анализ каждой критичной позиции
            master_dict = {blank.blank_sku: blank for blank in master_blanks}
            stock_dict = {stock.blank_sku: stock for stock in current_stocks}

            critical_items = []
            for recommendation in critical_recommendations:
                master = master_dict.get(recommendation.blank_sku)
                stock = stock_dict.get(recommendation.blank_sku)

                if not master or not stock:
                    continue

                analysis = self.stock_calculator.analyze_stock_position(
                    recommendation.blank_sku, stock, master
                )

                critical_items.append(analysis)

            # Формируем отчет
            report = {
                "report_type": "critical",
                "generated_at": datetime.now(),
                "total_critical_items": len(critical_items),
                "urgent_orders_needed": len([item for item in critical_items if item["urgency"] == "critical"]),
                "total_recommended_qty": sum(item["recommended_qty"] for item in critical_items),
                "critical_items": critical_items
            }

            logger.info(
                "Critical items report generated",
                critical_count=len(critical_items),
                urgent_orders=len([item for item in critical_items if item["urgency"] == "critical"])
            )

            return report

        except Exception as e:
            logger.error("Failed to generate critical items report", error=str(e))
            raise

    async def generate_movements_report(
        self,
        days_back: int = 7,
        blank_sku: str | None = None
    ) -> dict[str, Any]:
        """
        Генерация отчета по движениям товаров.
        
        Args:
            days_back: Количество дней назад для анализа
            blank_sku: Конкретный SKU (опционально)
            
        Returns:
            Dict[str, Any]: Отчет по движениям
        """

        try:
            logger.info(
                "Generating movements report",
                days_back=days_back,
                blank_sku=blank_sku
            )

            # Получаем движения
            movements = self.sheets_client.get_movements(blank_sku=blank_sku, limit=1000)

            # Фильтруем по дате
            cutoff_date = datetime.now() - timedelta(days=days_back)
            recent_movements = [
                movement for movement in movements
                if movement.timestamp >= cutoff_date
            ]

            # Анализируем движения
            movement_stats = {
                "receipts": {"count": 0, "total_qty": 0},
                "orders": {"count": 0, "total_qty": 0},
                "corrections": {"count": 0, "total_qty": 0}
            }

            movements_by_sku = {}
            movements_by_day = {}

            for movement in recent_movements:
                # Статистика по типам
                movement_type = movement.type.value
                if movement_type in movement_stats:
                    movement_stats[movement_type]["count"] += 1
                    movement_stats[movement_type]["total_qty"] += abs(movement.qty)

                # По SKU
                if movement.blank_sku not in movements_by_sku:
                    movements_by_sku[movement.blank_sku] = []
                movements_by_sku[movement.blank_sku].append({
                    "timestamp": movement.timestamp,
                    "type": movement.type.value,
                    "qty": movement.qty,
                    "balance_after": movement.balance_after,
                    "source": movement.source_type.value,
                    "note": movement.note
                })

                # По дням
                day_key = movement.timestamp.date().isoformat()
                if day_key not in movements_by_day:
                    movements_by_day[day_key] = {"receipts": 0, "orders": 0, "corrections": 0}

                if movement.type.value in movements_by_day[day_key]:
                    movements_by_day[day_key][movement.type.value] += abs(movement.qty)

            # Формируем отчет
            report = {
                "report_type": "movements",
                "generated_at": datetime.now(),
                "period": {
                    "days_back": days_back,
                    "from_date": cutoff_date.date(),
                    "to_date": datetime.now().date()
                },
                "filter": {"blank_sku": blank_sku} if blank_sku else None,
                "total_movements": len(recent_movements),
                "movement_stats": movement_stats,
                "movements_by_day": movements_by_day,
                "movements_by_sku": movements_by_sku,
                "top_active_skus": self._get_top_active_skus(movements_by_sku, limit=10)
            }

            logger.info(
                "Movements report generated",
                total_movements=len(recent_movements),
                period_days=days_back
            )

            return report

        except Exception as e:
            logger.error("Failed to generate movements report", error=str(e))
            raise

    # === МЕТОДЫ ДЛЯ TELEGRAM БОТА ===

    async def generate_summary_report(self) -> str:
        """Генерация краткого отчета для Telegram."""
        report = await self.generate_short_report()
        return self.format_report_for_telegram(report)
    
    async def generate_critical_stock_report(self) -> str:
        """Генерация отчета по критичным позициям для Telegram."""
        report = await self.generate_critical_items_report()
        return self.format_report_for_telegram(report)
    
    async def generate_full_stock_report(self) -> str:
        """Генерация полного отчета для Telegram."""
        report = await self.generate_full_report()
        return self.format_report_for_telegram(report)

    def format_report_for_telegram(
        self,
        report: dict[str, Any],
        max_length: int = 4000
    ) -> str:
        """
        Форматирование отчета для отправки в Telegram.
        
        Args:
            report: Данные отчета
            max_length: Максимальная длина сообщения
            
        Returns:
            str: Отформатированный текст отчета
        """

        report_type = report.get("report_type", "unknown")

        if report_type == "short":
            return self._format_short_report_telegram(report, max_length)
        elif report_type == "full":
            return self._format_full_report_telegram(report, max_length)
        elif report_type == "critical":
            return self._format_critical_report_telegram(report, max_length)
        else:
            return f"📊 Звіт типу '{report_type}' згенеровано успішно"

    def _format_short_report_telegram(self, report: dict[str, Any], max_length: int) -> str:
        """Форматирование краткого отчета для Telegram."""

        generated_at = report["generated_at"].strftime("%d.%m.%Y %H:%M")
        summary = report["summary"]

        text = "📋 <b>Короткий звіт по складу</b>\n"
        text += f"🗓️ {generated_at}\n\n"

        if summary["critical_count"] > 0:
            text += f"🔴 <b>Критично низький рівень ({summary['critical_count']}):</b>\n"
            for item in report["critical_items"]:
                sku_display = self._format_sku_display(item["blank_sku"])
                text += f"• {sku_display}: {item['on_hand']}/{item['min_level']} → замовити {item['recommended_qty']}\n"
            text += "\n"

        if summary["high_priority_count"] > 0:
            text += f"🟡 <b>Потребують уваги ({summary['high_priority_count']}):</b>\n"
            for item in report["high_priority_items"]:
                sku_display = self._format_sku_display(item["blank_sku"])
                text += f"• {sku_display}: {item['on_hand']}/{item['min_level']}\n"
            text += "\n"

        if summary["sufficient_count"] > 0:
            text += f"✅ <b>Достатній запас:</b> {summary['sufficient_count']} SKU\n\n"

        text += "📊 Детальний звіт: /report full"

        return text[:max_length]

    def _format_critical_report_telegram(self, report: dict[str, Any], max_length: int) -> str:
        """Форматирование отчета по критичным позициям для Telegram."""

        generated_at = report["generated_at"].strftime("%d.%m.%Y %H:%M")

        text = "🔴 <b>Критичні позиції</b>\n"
        text += f"🗓️ {generated_at}\n\n"

        if report["total_critical_items"] == 0:
            text += "✅ Критичних позицій немає!\nВсі заготовки в достатній кількості.\n"
        else:
            text += f"⚠️ <b>Всього критичних позицій:</b> {report['total_critical_items']}\n"
            text += f"🚨 <b>Потребують термінового замовлення:</b> {report['urgent_orders_needed']}\n\n"

            urgent_items = [item for item in report["critical_items"] if item["urgency"] == "critical"]
            if urgent_items:
                text += "🚨 <b>ТЕРМІНОВО замовити:</b>\n"
                for item in urgent_items:
                    sku_display = self._format_sku_display(item["blank_sku"])
                    text += f"• {sku_display}: {item['on_hand']}/{item['min_level']} → {item['recommended_qty']} шт\n"
                text += "\n"

            high_items = [item for item in report["critical_items"] if item["urgency"] == "high"]
            if high_items:
                text += "🟡 <b>Високий пріоритет:</b>\n"
                for item in high_items[:5]:  # Топ 5
                    sku_display = self._format_sku_display(item["blank_sku"])
                    text += f"• {sku_display}: {item['on_hand']}/{item['min_level']} → {item['recommended_qty']} шт\n"

        return text[:max_length]

    def _format_full_report_telegram(self, report: dict[str, Any], max_length: int) -> str:
        """Форматирование полного отчета для Telegram."""

        generated_at = report["generated_at"].strftime("%d.%m.%Y %H:%M")
        metrics = report["metrics"]

        text = "📄 <b>Повний звіт по складу</b>\n"
        text += f"🗓️ {generated_at}\n\n"

        text += "📊 <b>Загальна статистика:</b>\n"
        text += f"• Всього SKU: {metrics['total_skus']}\n"
        text += f"• З залишками: {metrics['skus_with_stock']}\n"
        text += f"• Нижче мінімуму: {metrics['skus_below_min']}\n"
        text += f"• Критичних: {metrics['skus_critical']}\n"
        text += f"• Всього одиниць: {metrics['total_units']}\n"
        text += f"• Ризик дефіциту: {metrics['stockout_risk_pct']}%\n\n"

        # Показываем по типам (сокращенно для Telegram)
        stock_by_type = report["stock_by_type"]
        for stock_type, items in stock_by_type.items():
            type_name = self._get_type_display_name(stock_type)
            items_below_min = [item for item in items if item["status"] != "sufficient"]

            text += f"{self._get_type_emoji(stock_type)} <b>{type_name}:</b>\n"

            if items_below_min:
                for item in items_below_min[:3]:  # Топ 3 проблемных
                    status_emoji = "🔴" if item["status"] == "critical" else "🟡"
                    text += f"  {status_emoji} {item['name_ua']}: {item['on_hand']} шт\n"
                if len(items_below_min) > 3:
                    text += f"  ...ще {len(items_below_min) - 3} позицій\n"
            else:
                text += "  ✅ Всі позиції в нормі\n"

            text += "\n"

        return text[:max_length]

    def _get_stock_status(self, on_hand: int, min_level: int) -> str:
        """Определение статуса остатка."""
        if on_hand <= min_level * 0.5:
            return "critical"
        elif on_hand <= min_level:
            return "low"
        else:
            return "sufficient"

    def _get_top_active_skus(self, movements_by_sku: dict[str, list], limit: int = 10) -> list[dict]:
        """Получение наиболее активных SKU по движениям."""

        activity_scores = {}
        for sku, movements in movements_by_sku.items():
            activity_scores[sku] = len(movements)

        # Сортируем по активности
        sorted_skus = sorted(activity_scores.items(), key=lambda x: x[1], reverse=True)

        return [
            {"blank_sku": sku, "movements_count": count}
            for sku, count in sorted_skus[:limit]
        ]

    def _format_sku_display(self, blank_sku: str) -> str:
        """Красивое отображение SKU для Telegram."""
        # Пример: BLK-HEART-25-GLD -> ❤️ Серце 25мм 🟡
        try:
            parts = blank_sku.split('-')
            if len(parts) != 4:
                return blank_sku

            _, sku_type, size, color = parts

            type_emojis = {
                "BONE": "🦴", "RING": "🟢", "ROUND": "⚪",
                "HEART": "❤️", "FLOWER": "🌸", "CLOUD": "☁️"
            }

            color_emojis = {"GLD": "🟡", "SIL": "⚪"}

            type_emoji = type_emojis.get(sku_type, "")
            color_emoji = color_emojis.get(color, "")

            return f"{type_emoji} {size}мм {color_emoji}"

        except Exception:
            return blank_sku

    def _get_type_display_name(self, stock_type: str) -> str:
        """Получение отображаемого названия типа."""
        type_names = {
            "BONE": "Кістка",
            "RING": "Бублик",
            "ROUND": "Круглий",
            "HEART": "Серце",
            "FLOWER": "Квітка",
            "CLOUD": "Хмарка"
        }
        return type_names.get(stock_type, stock_type)

    def _get_type_emoji(self, stock_type: str) -> str:
        """Получение emoji для типа заготовки."""
        type_emojis = {
            "BONE": "🦴", "RING": "🟢", "ROUND": "⚪",
            "HEART": "❤️", "FLOWER": "🌸", "CLOUD": "☁️"
        }
        return type_emojis.get(stock_type, "📦")


# Глобальный экземпляр сервиса
_report_service: ReportService | None = None


def get_report_service() -> ReportService:
    """Получение глобального экземпляра Report Service."""
    global _report_service

    if _report_service is None:
        _report_service = ReportService()

    return _report_service
