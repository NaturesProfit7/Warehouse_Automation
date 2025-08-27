"""Обработчики webhook событий."""

from datetime import datetime
from typing import Any

from ..core.exceptions import (
    DuplicateMovementError,
    IntegrationError,
    MappingError,
    StockCalculationError,
)
from ..core.models import MovementSourceType
from ..integrations.keycrm import get_keycrm_client
from ..services.stock_service import get_stock_service
from ..utils.logger import get_logger
from .auth import validate_keycrm_event

logger = get_logger(__name__)


class KeyCRMWebhookHandler:
    """Обработчик webhook событий от KeyCRM."""

    def __init__(self):
        self.stock_service = get_stock_service()
        logger.info("KeyCRM webhook handler initialized")

    async def handle_keycrm_webhook(
        self,
        payload: dict[str, Any],
        request_id: str
    ) -> dict[str, Any]:
        """
        Обработка webhook от KeyCRM.
        
        Args:
            payload: JSON данные webhook
            request_id: ID запроса для трассировки
            
        Returns:
            Dict[str, Any]: Результат обработки
            
        Raises:
            IntegrationError: При ошибке интеграции
        """

        try:
            logger.info(
                "Starting KeyCRM webhook processing",
                request_id=request_id,
                webhook_event=payload.get("event")
            )

            # Парсинг payload
            keycrm_client = await get_keycrm_client()
            webhook_data = keycrm_client.parse_webhook_payload(payload)

            # Валидация события - обрабатываем только создание заказов
            if not validate_keycrm_event(payload):
                logger.info(
                    "Webhook event skipped - waiting for order creation status",
                    request_id=request_id,
                    webhook_event=webhook_data.event,
                    order_id=webhook_data.order_id,
                    status=webhook_data.order_status
                )
                return {
                    "action": "skipped",
                    "reason": "Waiting for order creation status (new/created/pending)",
                    "event": webhook_data.event,
                    "order_id": webhook_data.order_id
                }

            # Получение полных данных заказа
            order = await keycrm_client.get_order(webhook_data.order_id)

            logger.info(
                "Order retrieved from KeyCRM",
                request_id=request_id,
                order_id=order.id,
                items_count=len(order.items),
                total=order.grand_total,
                client_id=order.client_id
            )

            # Обработка движений по заказу
            try:
                movements = await self.stock_service.process_order_movement(
                    order=order,
                    source_type=MovementSourceType.KEYCRM_WEBHOOK
                )

                # Подготовка результата
                result = {
                    "action": "processed",
                    "order_id": order.id,
                    "movements_created": len(movements),
                    "movements": []
                }

                # Добавляем детали движений
                for movement in movements:
                    result["movements"].append({
                        "blank_sku": movement.blank_sku,
                        "quantity": movement.qty,
                        "balance_after": movement.balance_after,
                        "movement_id": str(movement.id)
                    })

                logger.info(
                    "Order movements processed successfully",
                    request_id=request_id,
                    order_id=order.id,
                    movements_created=len(movements)
                )

                return result

            except DuplicateMovementError as e:
                logger.warning(
                    "Duplicate movement detected",
                    request_id=request_id,
                    order_id=order.id,
                    error=str(e)
                )

                return {
                    "action": "duplicate",
                    "order_id": order.id,
                    "reason": "Order already processed",
                    "error": str(e)
                }

            except MappingError as e:
                logger.error(
                    "Mapping error processing order",
                    request_id=request_id,
                    order_id=order.id,
                    error=str(e)
                )

                # Возвращаем успех, но отмечаем проблему маппинга
                return {
                    "action": "partial",
                    "order_id": order.id,
                    "reason": "Some items could not be mapped",
                    "error": str(e)
                }

            except StockCalculationError as e:
                logger.error(
                    "Stock calculation error",
                    request_id=request_id,
                    order_id=order.id,
                    error=str(e)
                )

                # Это критическая ошибка - возвращаем 500 для retry
                raise IntegrationError(f"Stock calculation failed: {str(e)}")

        except IntegrationError:
            # Пробрасываем IntegrationError для обработки на уровне FastAPI
            raise

        except Exception as e:
            logger.error(
                "Unexpected error processing KeyCRM webhook",
                request_id=request_id,
                error=str(e),
                error_type=type(e).__name__
            )

            # Критическая ошибка - возвращаем 500 для retry
            raise IntegrationError(f"Unexpected error processing webhook: {str(e)}")

    async def handle_order_confirmed(
        self,
        order_id: int,
        request_id: str
    ) -> dict[str, Any]:
        """
        Обработка подтверждения заказа.
        
        Args:
            order_id: ID заказа
            request_id: ID запроса
            
        Returns:
            Dict[str, Any]: Результат обработки
        """

        try:
            logger.info(
                "Processing confirmed order",
                request_id=request_id,
                order_id=order_id
            )

            # Получение заказа
            keycrm_client = await get_keycrm_client()
            order = await keycrm_client.get_order(order_id)

            # Проверка статуса
            if order.status != "confirmed":
                logger.warning(
                    "Order status is not confirmed",
                    request_id=request_id,
                    order_id=order_id,
                    actual_status=order.status
                )
                return {
                    "action": "skipped",
                    "reason": f"Order status is {order.status}, not confirmed"
                }

            # Обработка движений
            movements = await self.stock_service.process_order_movement(
                order=order,
                source_type=MovementSourceType.KEYCRM_WEBHOOK
            )

            logger.info(
                "Confirmed order processed",
                request_id=request_id,
                order_id=order_id,
                movements=len(movements)
            )

            return {
                "action": "processed",
                "order_id": order_id,
                "movements_created": len(movements)
            }

        except Exception as e:
            logger.error(
                "Error processing confirmed order",
                request_id=request_id,
                order_id=order_id,
                error=str(e)
            )
            raise IntegrationError(f"Failed to process confirmed order: {str(e)}")

    async def get_processing_stats(self) -> dict[str, Any]:
        """
        Получение статистики обработки webhook.
        
        Returns:
            Dict[str, Any]: Статистика
        """

        try:
            # Получаем актуальные данные через stock service
            current_stock = await self.stock_service.get_all_current_stock()

            # Базовая статистика
            total_skus = len(current_stock)
            skus_with_stock = sum(1 for stock in current_stock if stock.on_hand > 0)
            total_units = sum(stock.on_hand for stock in current_stock)

            # Находим критичные позиции (нужно получить min levels из Master_Blanks)
            critical_skus = []  # TODO: реализовать логику определения критичных

            stats = {
                "timestamp": datetime.now().isoformat(),
                "total_skus": total_skus,
                "skus_with_stock": skus_with_stock,
                "total_units_on_hand": total_units,
                "critical_skus_count": len(critical_skus),
                "avg_stock_per_sku": round(total_units / total_skus, 2) if total_skus > 0 else 0
            }

            logger.debug("Processing stats generated", **stats)
            return stats

        except Exception as e:
            logger.error("Error getting processing stats", error=str(e))
            return {
                "timestamp": datetime.now().isoformat(),
                "error": "Failed to generate stats"
            }


class WebhookEventLogger:
    """Логгер для событий webhook с метриками."""

    def __init__(self):
        self.processed_count = 0
        self.error_count = 0
        self.skipped_count = 0
        self.start_time = datetime.now()

    def log_processed(self, order_id: int, movements_count: int):
        """Логирование успешной обработки."""
        self.processed_count += 1

        logger.info(
            "Webhook processed successfully",
            order_id=order_id,
            movements_count=movements_count,
            total_processed=self.processed_count
        )

    def log_error(self, order_id: int | None, error: str, error_type: str):
        """Логирование ошибки."""
        self.error_count += 1

        logger.error(
            "Webhook processing error",
            order_id=order_id,
            error=error,
            error_type=error_type,
            total_errors=self.error_count
        )

    def log_skipped(self, reason: str, order_id: int | None = None):
        """Логирование пропуска события."""
        self.skipped_count += 1

        logger.info(
            "Webhook event skipped",
            reason=reason,
            order_id=order_id,
            total_skipped=self.skipped_count
        )

    def get_stats(self) -> dict[str, Any]:
        """Получение статистики логгера."""
        uptime = (datetime.now() - self.start_time).total_seconds()

        return {
            "uptime_seconds": uptime,
            "processed_count": self.processed_count,
            "error_count": self.error_count,
            "skipped_count": self.skipped_count,
            "total_requests": self.processed_count + self.error_count + self.skipped_count,
            "success_rate": self.processed_count / max(1, self.processed_count + self.error_count) * 100
        }


# Глобальный экземпляр логгера событий
webhook_event_logger = WebhookEventLogger()
