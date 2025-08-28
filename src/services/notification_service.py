"""Сервис уведомлений о критических событиях."""

from datetime import datetime, timedelta
from typing import List, Optional
import asyncio

import httpx
from pydantic import BaseModel

from ..config import settings
from ..core.models import UrgencyLevel, CurrentStock, ReplenishmentRecommendation
from ..core.calculations import get_stock_calculator
from ..integrations.sheets import get_sheets_client
from ..services.stock_service import get_stock_service
from ..utils.logger import get_logger

logger = get_logger(__name__)


class NotificationConfig(BaseModel):
    """Конфигурация уведомлений."""
    
    critical_threshold_hours: int = 1  # Уведомления о критичных каждый час
    high_threshold_hours: int = 8      # Уведомления о важных каждые 8 часов
    daily_summary_enabled: bool = True  # Ежедневная сводка
    daily_summary_hour: int = 10       # Час отправки ежедневной сводки (10:30)
    
    # Фильтры для уведомлений
    min_critical_items: int = 1        # Минимум критичных позиций для уведомления
    max_items_per_message: int = 10    # Максимум позиций в одном сообщении


class CriticalStockAlert(BaseModel):
    """Уведомление о критичных остатках."""
    
    alert_type: str
    timestamp: datetime
    critical_items: List[ReplenishmentRecommendation]
    high_priority_items: List[ReplenishmentRecommendation]
    total_items_count: int
    message: str


class NotificationService:
    """Сервис отправки уведомлений о критических событиях."""
    
    def __init__(self):
        self.config = NotificationConfig()
        self.stock_calculator = get_stock_calculator()
        self.stock_service = get_stock_service()
        self.sheets_client = get_sheets_client()
        self._last_alerts = {}  # Кэш последних уведомлений по типу
        
        logger.info("Notification service initialized", config=self.config.model_dump())
    
    async def check_critical_stock(self) -> Optional[CriticalStockAlert]:
        """
        Проверка критичных остатков и формирование уведомления.
        
        Returns:
            Optional[CriticalStockAlert]: Уведомление или None
        """
        try:
            logger.debug("Checking critical stock levels")
            
            # Получаем текущие остатки и мастер-заготовки
            current_stocks = await self.stock_service.get_all_current_stock()
            master_blanks = self.sheets_client.get_master_blanks()
            
            # Рассчитываем рекомендации
            recommendations = self.stock_calculator.calculate_replenishment_needs(
                current_stocks, master_blanks
            )
            
            # Фильтруем по критичности
            critical_items = [r for r in recommendations if r.urgency == UrgencyLevel.CRITICAL]
            high_priority_items = [r for r in recommendations if r.urgency == UrgencyLevel.HIGH]
            
            # Проверяем нужно ли отправлять уведомление
            if len(critical_items) < self.config.min_critical_items:
                logger.debug("No critical items found, skipping notification")
                return None
            
            # Проверяем дедупликацию (не отправляем слишком часто)
            if not self._should_send_critical_alert(critical_items, high_priority_items):
                return None
            
            # Формируем уведомление
            alert = CriticalStockAlert(
                alert_type="critical_stock",
                timestamp=datetime.now(),
                critical_items=critical_items[:self.config.max_items_per_message],
                high_priority_items=high_priority_items[:self.config.max_items_per_message],
                total_items_count=len(critical_items) + len(high_priority_items),
                message=self._format_critical_alert_message(critical_items, high_priority_items)
            )
            
            # Обновляем кэш
            self._last_alerts["critical_stock"] = datetime.now()
            
            logger.info(
                "Critical stock alert generated",
                critical_count=len(critical_items),
                high_priority_count=len(high_priority_items)
            )
            
            return alert
            
        except Exception as e:
            logger.error("Failed to check critical stock", error=str(e))
            return None
    
    async def send_telegram_alert(self, alert: CriticalStockAlert) -> bool:
        """
        Отправка уведомления в Telegram.
        
        Args:
            alert: Уведомление для отправки
            
        Returns:
            bool: True если отправлено успешно
        """
        try:
            if not settings.TELEGRAM_BOT_TOKEN:
                logger.warning("Telegram bot token not configured, skipping notification")
                return False
            
            # Формируем список админов для отправки
            admin_ids = settings.TELEGRAM_ADMIN_USERS
            if not admin_ids:
                logger.warning("No admin user IDs configured, skipping notification")
                return False
            
            # Отправляем уведомление всем админам
            success_count = 0
            
            for admin_id in admin_ids:
                try:
                    await self._send_telegram_message(admin_id, alert.message)
                    success_count += 1
                    logger.debug("Alert sent to admin", admin_id=admin_id)
                except Exception as e:
                    logger.error("Failed to send alert to admin", admin_id=admin_id, error=str(e))
            
            logger.info(
                "Telegram alerts sent",
                alert_type=alert.alert_type,
                total_admins=len(admin_ids),
                successful_sends=success_count
            )
            
            return success_count > 0
            
        except Exception as e:
            logger.error("Failed to send telegram alert", error=str(e))
            return False
    
    async def generate_daily_summary(self) -> Optional[str]:
        """
        Генерация ежедневной сводки по остаткам.
        
        Returns:
            Optional[str]: Сообщение сводки или None
        """
        try:
            logger.debug("Generating daily summary")
            
            # Получаем данные
            current_stocks = await self.stock_service.get_all_current_stock()
            master_blanks = self.sheets_client.get_master_blanks()
            recommendations = self.stock_calculator.calculate_replenishment_needs(
                current_stocks, master_blanks
            )
            
            # Статистика
            total_skus = len(current_stocks)
            critical_count = sum(1 for r in recommendations if r.urgency == UrgencyLevel.CRITICAL)
            high_count = sum(1 for r in recommendations if r.urgency == UrgencyLevel.HIGH)
            need_order_count = sum(1 for r in recommendations if r.need_order)
            
            total_value = sum(s.on_hand for s in current_stocks)
            low_stock_count = sum(1 for s in current_stocks if s.on_hand < 50)
            
            # Формируем сообщение
            summary = f"""📊 <b>Ежедневная сводка склада</b>
📅 {datetime.now().strftime('%d.%m.%Y')}

📦 <b>Общая статистика:</b>
• Всего SKU: {total_skus}
• Общий остаток: {total_value} шт
• Позиций с остатком &lt;50: {low_stock_count}

⚠️ <b>Требуют внимания:</b>
• Критичные: {critical_count} позиций
• Важные: {high_count} позиций
• Всего к заказу: {need_order_count} позиций"""
            
            # Добавляем топ критичных если есть
            if critical_count > 0:
                critical_items = [r for r in recommendations if r.urgency == UrgencyLevel.CRITICAL]
                summary += "\n\n🚨 <b>Критичные остатки:</b>"
                
                for item in critical_items[:5]:  # Показываем только топ 5
                    summary += f"\n• {item.blank_sku}: {item.on_hand} шт"
                
                if len(critical_items) > 5:
                    summary += f"\n• ... и еще {len(critical_items) - 5} позиций"
            
            summary += "\n\n💡 Используйте /report для детального анализа"
            
            logger.info("Daily summary generated", 
                       total_skus=total_skus, 
                       critical_count=critical_count,
                       need_order_count=need_order_count)
            
            return summary
            
        except Exception as e:
            logger.error("Failed to generate daily summary", error=str(e))
            return None
    
    def _should_send_critical_alert(
        self, 
        critical_items: List[ReplenishmentRecommendation],
        high_priority_items: List[ReplenishmentRecommendation]
    ) -> bool:
        """Проверка нужно ли отправлять критичное уведомление (дедупликация)."""
        
        last_alert = self._last_alerts.get("critical_stock")
        if not last_alert:
            return True  # Первое уведомление
        
        # Проверяем прошло ли достаточно времени
        hours_since_last = (datetime.now() - last_alert).total_seconds() / 3600
        
        if critical_items and hours_since_last >= self.config.critical_threshold_hours:
            return True
            
        if high_priority_items and hours_since_last >= self.config.high_threshold_hours:
            return True
            
        return False
    
    def _format_critical_alert_message(
        self,
        critical_items: List[ReplenishmentRecommendation],
        high_priority_items: List[ReplenishmentRecommendation]
    ) -> str:
        """Форматирование сообщения о критичных остатках."""
        
        message = "🚨 <b>КРИТИЧНЫЕ ОСТАТКИ!</b>\n\n"
        
        if critical_items:
            message += f"⛔ <b>Критичные ({len(critical_items)}):</b>\n"
            for item in critical_items:
                stockout_info = ""
                if item.estimated_stockout:
                    days_left = (item.estimated_stockout - datetime.now().date()).days
                    if days_left <= 0:
                        stockout_info = " (уже закончился)"
                    else:
                        stockout_info = f" ({days_left}д. до исчерпания)"
                
                message += f"• <b>{item.blank_sku}</b>: {item.on_hand} шт{stockout_info}\n"
        
        if high_priority_items:
            message += f"\n⚠️ <b>Важные ({len(high_priority_items)}):</b>\n"
            for item in high_priority_items:
                message += f"• {item.blank_sku}: {item.on_hand} шт\n"
        
        message += f"\n💡 Используйте /report для детального анализа"
        
        return message
    
    async def _send_telegram_message(self, chat_id: int, message: str) -> None:
        """Отправка сообщения в Telegram."""
        
        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        
        data = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=data, timeout=30.0)
            response.raise_for_status()


# Глобальный экземпляр сервиса
_notification_service: NotificationService | None = None


def get_notification_service() -> NotificationService:
    """Получение глобального экземпляра NotificationService."""
    global _notification_service
    
    if _notification_service is None:
        _notification_service = NotificationService()
    
    return _notification_service