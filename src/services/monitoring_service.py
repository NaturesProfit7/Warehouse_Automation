"""Сервис мониторинга состояния системы."""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

import httpx
from pydantic import BaseModel

from ..config import settings
from ..utils.logger import get_logger
from ..integrations.sheets import get_sheets_client
from .stock_service import get_stock_service
from .notification_service import get_notification_service

logger = get_logger(__name__)


class ComponentStatus(str, Enum):
    """Статусы компонентов системы."""
    HEALTHY = "healthy"
    WARNING = "warning" 
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class ComponentHealth:
    """Состояние компонента системы."""
    name: str
    status: ComponentStatus
    response_time_ms: Optional[int] = None
    last_check: Optional[datetime] = None
    error_message: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


class SystemHealth(BaseModel):
    """Общее состояние системы."""
    overall_status: ComponentStatus
    check_timestamp: datetime
    components: Dict[str, ComponentHealth]
    uptime_seconds: int
    alerts_count: int
    warnings_count: int
    
    class Config:
        arbitrary_types_allowed = True


class MonitoringService:
    """Сервис мониторинга системы."""
    
    def __init__(self):
        self.start_time = datetime.now()
        self.health_history: List[SystemHealth] = []
        self.max_history_entries = 100  # Храним последние 100 проверок
        
        # Компоненты для мониторинга
        self.components = {
            "telegram_bot": self._check_telegram_bot,
            "google_sheets": self._check_google_sheets,
            "stock_service": self._check_stock_service,
            "notification_service": self._check_notification_service,
            "database_sheets": self._check_database_health
        }
        
        logger.info("Monitoring service initialized", components=list(self.components.keys()))
    
    async def perform_health_check(self) -> SystemHealth:
        """Выполнение полной проверки состояния системы."""
        logger.debug("Starting system health check")
        start_time = datetime.now()
        
        # Проверяем все компоненты параллельно
        tasks = {}
        for component_name, check_func in self.components.items():
            tasks[component_name] = asyncio.create_task(
                self._safe_component_check(component_name, check_func)
            )
        
        # Ждем результаты всех проверок
        component_results = {}
        for component_name, task in tasks.items():
            component_results[component_name] = await task
        
        # Определяем общий статус
        overall_status = self._calculate_overall_status(component_results)
        
        # Подсчитываем количество проблем
        alerts_count = sum(
            1 for health in component_results.values() 
            if health.status == ComponentStatus.CRITICAL
        )
        warnings_count = sum(
            1 for health in component_results.values() 
            if health.status == ComponentStatus.WARNING
        )
        
        # Создаем результат
        health = SystemHealth(
            overall_status=overall_status,
            check_timestamp=datetime.now(),
            components=component_results,
            uptime_seconds=int((datetime.now() - self.start_time).total_seconds()),
            alerts_count=alerts_count,
            warnings_count=warnings_count
        )
        
        # Сохраняем в историю
        self._save_to_history(health)
        
        check_duration = (datetime.now() - start_time).total_seconds()
        logger.info(
            "System health check completed",
            overall_status=overall_status.value,
            alerts=alerts_count,
            warnings=warnings_count,
            duration_seconds=round(check_duration, 2)
        )
        
        return health
    
    async def _safe_component_check(self, component_name: str, check_func) -> ComponentHealth:
        """Безопасная проверка компонента с обработкой ошибок."""
        start_time = datetime.now()
        
        try:
            result = await check_func()
            response_time = int((datetime.now() - start_time).total_seconds() * 1000)
            
            if isinstance(result, ComponentHealth):
                result.response_time_ms = response_time
                result.last_check = datetime.now()
                return result
            else:
                # Если возвращен простой статус
                return ComponentHealth(
                    name=component_name,
                    status=result if isinstance(result, ComponentStatus) else ComponentStatus.HEALTHY,
                    response_time_ms=response_time,
                    last_check=datetime.now()
                )
                
        except Exception as e:
            logger.error(f"Health check failed for {component_name}", error=str(e))
            return ComponentHealth(
                name=component_name,
                status=ComponentStatus.CRITICAL,
                response_time_ms=None,
                last_check=datetime.now(),
                error_message=str(e)
            )
    
    async def _check_telegram_bot(self) -> ComponentHealth:
        """Проверка состояния Telegram Bot API."""
        if not settings.TELEGRAM_BOT_TOKEN:
            return ComponentHealth(
                name="telegram_bot",
                status=ComponentStatus.CRITICAL,
                error_message="Telegram bot token not configured"
            )
        
        try:
            url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/getMe"
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=10.0)
                
                if response.status_code == 200:
                    bot_info = response.json()
                    return ComponentHealth(
                        name="telegram_bot",
                        status=ComponentStatus.HEALTHY,
                        details={
                            "bot_username": bot_info.get("result", {}).get("username"),
                            "bot_id": bot_info.get("result", {}).get("id")
                        }
                    )
                else:
                    return ComponentHealth(
                        name="telegram_bot",
                        status=ComponentStatus.CRITICAL,
                        error_message=f"HTTP {response.status_code}"
                    )
                    
        except httpx.TimeoutException:
            return ComponentHealth(
                name="telegram_bot",
                status=ComponentStatus.WARNING,
                error_message="Request timeout"
            )
        except Exception as e:
            return ComponentHealth(
                name="telegram_bot",
                status=ComponentStatus.CRITICAL,
                error_message=str(e)
            )
    
    async def _check_google_sheets(self) -> ComponentHealth:
        """Проверка доступности Google Sheets."""
        try:
            sheets_client = get_sheets_client()
            
            # Пытаемся получить мастер-заготовки
            master_blanks = sheets_client.get_master_blanks()
            
            if len(master_blanks) == 0:
                return ComponentHealth(
                    name="google_sheets",
                    status=ComponentStatus.WARNING,
                    error_message="No master blanks found"
                )
            
            # Пытаемся получить движения
            movements = sheets_client.get_movements()
            
            return ComponentHealth(
                name="google_sheets",
                status=ComponentStatus.HEALTHY,
                details={
                    "master_blanks_count": len(master_blanks),
                    "movements_count": len(movements)
                }
            )
            
        except Exception as e:
            return ComponentHealth(
                name="google_sheets",
                status=ComponentStatus.CRITICAL,
                error_message=str(e)
            )
    
    async def _check_stock_service(self) -> ComponentHealth:
        """Проверка работоспособности сервиса остатков."""
        try:
            stock_service = get_stock_service()
            
            # Проверяем получение текущих остатков
            current_stocks = await stock_service.get_all_current_stock()
            
            if len(current_stocks) == 0:
                return ComponentHealth(
                    name="stock_service",
                    status=ComponentStatus.WARNING,
                    error_message="No stock data available"
                )
            
            return ComponentHealth(
                name="stock_service",
                status=ComponentStatus.HEALTHY,
                details={
                    "stock_items_count": len(current_stocks),
                    "last_service_call": "get_all_current_stock"
                }
            )
            
        except Exception as e:
            return ComponentHealth(
                name="stock_service",
                status=ComponentStatus.CRITICAL,
                error_message=str(e)
            )
    
    async def _check_notification_service(self) -> ComponentHealth:
        """Проверка сервиса уведомлений."""
        try:
            notification_service = get_notification_service()
            
            # Проверяем конфигурацию
            config = notification_service.config
            
            status = ComponentStatus.HEALTHY
            details = {
                "critical_threshold_hours": config.critical_threshold_hours,
                "high_threshold_hours": config.high_threshold_hours,
                "daily_summary_enabled": config.daily_summary_enabled
            }
            
            # Проверяем наличие админов для уведомлений
            if not settings.TELEGRAM_ADMIN_USERS:
                status = ComponentStatus.WARNING
                details["warning"] = "No admin user IDs configured"
            
            return ComponentHealth(
                name="notification_service",
                status=status,
                details=details
            )
            
        except Exception as e:
            return ComponentHealth(
                name="notification_service",
                status=ComponentStatus.CRITICAL,
                error_message=str(e)
            )
    
    async def _check_database_health(self) -> ComponentHealth:
        """Проверка состояния данных в Google Sheets."""
        try:
            sheets_client = get_sheets_client()
            
            # Проверяем свежесть данных
            movements = sheets_client.get_movements()
            
            if not movements:
                return ComponentHealth(
                    name="database_sheets",
                    status=ComponentStatus.WARNING,
                    error_message="No movement data found"
                )
            
            # Проверяем есть ли недавние движения (за последние 7 дней)
            recent_cutoff = datetime.now() - timedelta(days=7)
            recent_movements = [
                m for m in movements 
                if m.timestamp >= recent_cutoff
            ]
            
            status = ComponentStatus.HEALTHY
            if len(recent_movements) == 0:
                status = ComponentStatus.WARNING
            
            return ComponentHealth(
                name="database_sheets",
                status=status,
                details={
                    "total_movements": len(movements),
                    "recent_movements_7d": len(recent_movements),
                    "oldest_movement": min(m.timestamp for m in movements) if movements else None,
                    "newest_movement": max(m.timestamp for m in movements) if movements else None
                }
            )
            
        except Exception as e:
            return ComponentHealth(
                name="database_sheets",
                status=ComponentStatus.CRITICAL,
                error_message=str(e)
            )
    
    
    def _calculate_overall_status(self, components: Dict[str, ComponentHealth]) -> ComponentStatus:
        """Расчет общего статуса системы на основе компонентов."""
        statuses = [health.status for health in components.values()]
        
        # Если есть критические проблемы - система критична
        if ComponentStatus.CRITICAL in statuses:
            return ComponentStatus.CRITICAL
        
        # Если есть предупреждения - система в состоянии предупреждения  
        if ComponentStatus.WARNING in statuses:
            return ComponentStatus.WARNING
        
        # Если есть неизвестные статусы - предупреждение
        if ComponentStatus.UNKNOWN in statuses:
            return ComponentStatus.WARNING
        
        # Иначе система здорова
        return ComponentStatus.HEALTHY
    
    def _save_to_history(self, health: SystemHealth) -> None:
        """Сохранение результата проверки в историю."""
        self.health_history.append(health)
        
        # Ограничиваем размер истории
        if len(self.health_history) > self.max_history_entries:
            self.health_history = self.health_history[-self.max_history_entries:]
    
    def get_health_history(self, hours: int = 24) -> List[SystemHealth]:
        """Получение истории состояния за указанный период."""
        cutoff = datetime.now() - timedelta(hours=hours)
        return [
            health for health in self.health_history
            if health.check_timestamp >= cutoff
        ]
    
    def get_component_trends(self, component_name: str, hours: int = 24) -> Dict[str, Any]:
        """Получение трендов для конкретного компонента."""
        history = self.get_health_history(hours)
        
        if not history:
            return {"error": "No history data available"}
        
        component_history = []
        for health_check in history:
            if component_name in health_check.components:
                component_health = health_check.components[component_name]
                component_history.append({
                    "timestamp": health_check.check_timestamp,
                    "status": component_health.status.value,
                    "response_time_ms": component_health.response_time_ms,
                    "error": component_health.error_message
                })
        
        if not component_history:
            return {"error": f"No history for component {component_name}"}
        
        # Рассчитываем статистику
        statuses = [item["status"] for item in component_history]
        response_times = [item["response_time_ms"] for item in component_history if item["response_time_ms"]]
        
        return {
            "component_name": component_name,
            "period_hours": hours,
            "total_checks": len(component_history),
            "status_distribution": {
                status: statuses.count(status) for status in set(statuses)
            },
            "avg_response_time_ms": sum(response_times) / len(response_times) if response_times else None,
            "max_response_time_ms": max(response_times) if response_times else None,
            "recent_errors": [
                item for item in component_history[-10:] if item["error"]
            ]
        }
    
    def get_system_summary(self) -> Dict[str, Any]:
        """Получение краткой сводки состояния системы."""
        if not self.health_history:
            return {"error": "No health data available"}
        
        latest = self.health_history[-1]
        
        return {
            "overall_status": latest.overall_status.value,
            "last_check": latest.check_timestamp.isoformat(),
            "uptime_seconds": latest.uptime_seconds,
            "uptime_hours": round(latest.uptime_seconds / 3600, 1),
            "alerts_count": latest.alerts_count,
            "warnings_count": latest.warnings_count,
            "total_components": len(latest.components),
            "healthy_components": sum(
                1 for health in latest.components.values()
                if health.status == ComponentStatus.HEALTHY
            ),
            "component_summary": {
                name: {
                    "status": health.status.value,
                    "response_time_ms": health.response_time_ms
                }
                for name, health in latest.components.items()
            }
        }


# Глобальный экземпляр сервиса мониторинга
_monitoring_service: Optional[MonitoringService] = None


def get_monitoring_service() -> MonitoringService:
    """Получение глобального экземпляра сервиса мониторинга."""
    global _monitoring_service
    
    if _monitoring_service is None:
        _monitoring_service = MonitoringService()
    
    return _monitoring_service