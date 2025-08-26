"""KeyCRM API клиент для работы с заказами."""

import hashlib
import hmac
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any, Union
from uuid import uuid4

import httpx
from pydantic import BaseModel, Field

from ..config import settings
from ..core.models import KeyCRMWebhookPayload, ProductMapping
from ..core.exceptions import IntegrationError
from ..utils.logger import get_logger
from ..utils.retry import retry_with_backoff

logger = get_logger(__name__)


class KeyCRMOrderItem(BaseModel):
    """Позиция заказа KeyCRM."""
    
    id: int = Field(..., description="ID позиции")
    product_id: int = Field(..., description="ID товара")
    product_name: str = Field(..., description="Название товара")
    quantity: int = Field(..., description="Количество")
    price: float = Field(..., description="Цена за единицу")
    total: float = Field(..., description="Общая стоимость")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Свойства товара")


class KeyCRMOrder(BaseModel):
    """Заказ KeyCRM."""
    
    id: int = Field(..., description="ID заказа")
    status: str = Field(..., description="Статус заказа")
    created_at: datetime = Field(..., description="Дата создания")
    updated_at: datetime = Field(..., description="Дата обновления")
    client_id: int = Field(..., description="ID клиента")
    grand_total: float = Field(..., description="Общая сумма")
    items: List[KeyCRMOrderItem] = Field(default_factory=list, description="Позиции заказа")
    
    # Дополнительные поля из KeyCRM
    client_name: Optional[str] = Field(default=None, description="Имя клиента")
    client_phone: Optional[str] = Field(default=None, description="Телефон клиента")
    delivery_address: Optional[str] = Field(default=None, description="Адрес доставки")
    notes: Optional[str] = Field(default=None, description="Примечания")


class KeyCRMClient:
    """Клиент для работы с KeyCRM API."""
    
    def __init__(self):
        self.base_url = settings.KEYCRM_API_URL
        self.api_token = settings.KEYCRM_API_TOKEN
        self.webhook_secret = settings.KEYCRM_WEBHOOK_SECRET
        
        # Настройка HTTP клиента
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json"
            }
        )
        
        logger.info("KeyCRM client initialized", base_url=self.base_url)
    
    async def close(self) -> None:
        """Закрытие HTTP клиента."""
        await self.client.aclose()
    
    @retry_with_backoff(max_retries=3)
    async def get_order(self, order_id: int) -> KeyCRMOrder:
        """
        Получение заказа по ID.
        
        Args:
            order_id: ID заказа в KeyCRM
            
        Returns:
            KeyCRMOrder: Данные заказа
            
        Raises:
            IntegrationError: При ошибке API KeyCRM
        """
        try:
            logger.debug("Fetching order from KeyCRM", order_id=order_id)
            
            response = await self.client.get(f"/orders/{order_id}")
            response.raise_for_status()
            
            data = response.json()
            
            # Преобразуем данные в модель
            order = self._parse_order_response(data)
            
            logger.info("Order fetched successfully", order_id=order_id, items_count=len(order.items))
            return order
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise IntegrationError(f"Order {order_id} not found in KeyCRM")
            
            logger.error(
                "KeyCRM API error",
                order_id=order_id,
                status_code=e.response.status_code,
                response_text=e.response.text
            )
            raise IntegrationError(f"KeyCRM API error: {e.response.status_code}")
            
        except Exception as e:
            logger.error("Failed to fetch order", order_id=order_id, error=str(e))
            raise IntegrationError(f"Failed to fetch order {order_id}: {str(e)}")
    
    @retry_with_backoff(max_retries=3)
    async def get_orders_by_date_range(
        self,
        start_date: date,
        end_date: date,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[KeyCRMOrder]:
        """
        Получение заказов за период.
        
        Args:
            start_date: Начальная дата
            end_date: Конечная дата
            status: Фильтр по статусу (например, "confirmed")
            limit: Максимальное количество заказов
            
        Returns:
            List[KeyCRMOrder]: Список заказов
        """
        try:
            params = {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "limit": limit
            }
            
            if status:
                params["status"] = status
            
            logger.debug(
                "Fetching orders by date range",
                start_date=start_date,
                end_date=end_date,
                status=status,
                limit=limit
            )
            
            response = await self.client.get("/orders", params=params)
            response.raise_for_status()
            
            data = response.json()
            orders = []
            
            for order_data in data.get("orders", []):
                order = self._parse_order_response(order_data)
                orders.append(order)
            
            logger.info(
                "Orders fetched successfully",
                count=len(orders),
                date_range=f"{start_date} to {end_date}"
            )
            
            return orders
            
        except Exception as e:
            logger.error(
                "Failed to fetch orders by date range",
                start_date=start_date,
                end_date=end_date,
                error=str(e)
            )
            raise IntegrationError(f"Failed to fetch orders: {str(e)}")
    
    @retry_with_backoff(max_retries=3)
    async def get_confirmed_orders_since(
        self,
        since_date: date,
        limit: int = 100
    ) -> List[KeyCRMOrder]:
        """
        Получение подтвержденных заказов с указанной даты.
        
        Args:
            since_date: Дата начала поиска
            limit: Максимальное количество заказов
            
        Returns:
            List[KeyCRMOrder]: Список подтвержденных заказов
        """
        end_date = date.today()
        return await self.get_orders_by_date_range(
            start_date=since_date,
            end_date=end_date,
            status="confirmed",
            limit=limit
        )
    
    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        Проверка HMAC подписи вебхука.
        
        Args:
            payload: Тело запроса (bytes)
            signature: HMAC подпись из заголовка
            
        Returns:
            bool: True если подпись валидна
        """
        try:
            # KeyCRM отправляет подпись в формате sha256=<hash>
            if not signature.startswith('sha256='):
                logger.warning("Invalid signature format", signature=signature)
                return False
            
            expected_signature = signature[7:]  # Убираем "sha256="
            
            # Вычисляем HMAC
            calculated_signature = hmac.new(
                self.webhook_secret.encode('utf-8'),
                payload,
                hashlib.sha256
            ).hexdigest()
            
            # Безопасное сравнение
            is_valid = hmac.compare_digest(calculated_signature, expected_signature)
            
            logger.debug(
                "Webhook signature verification",
                is_valid=is_valid,
                signature_length=len(signature)
            )
            
            return is_valid
            
        except Exception as e:
            logger.error("Error verifying webhook signature", error=str(e))
            return False
    
    def parse_webhook_payload(self, payload: Dict[str, Any]) -> KeyCRMWebhookPayload:
        """
        Парсинг payload вебхука.
        
        Args:
            payload: JSON данные вебхука
            
        Returns:
            KeyCRMWebhookPayload: Распарсенные данные
        """
        try:
            webhook_data = KeyCRMWebhookPayload(**payload)
            
            logger.debug(
                "Webhook payload parsed",
                event=webhook_data.event,
                order_id=webhook_data.order_id,
                status=webhook_data.order_status
            )
            
            return webhook_data
            
        except Exception as e:
            logger.error("Failed to parse webhook payload", error=str(e), payload=payload)
            raise IntegrationError(f"Invalid webhook payload: {str(e)}")
    
    def _parse_order_response(self, data: Dict[str, Any]) -> KeyCRMOrder:
        """Парсинг ответа API заказа в модель."""
        
        try:
            # Парсинг позиций заказа
            items = []
            for item_data in data.get("order_items", []):
                item = KeyCRMOrderItem(
                    id=item_data.get("id"),
                    product_id=item_data.get("product_id"),
                    product_name=item_data.get("product_name", ""),
                    quantity=item_data.get("quantity", 0),
                    price=float(item_data.get("price", 0)),
                    total=float(item_data.get("total", 0)),
                    properties=item_data.get("properties", {})
                )
                items.append(item)
            
            # Парсинг заказа
            order = KeyCRMOrder(
                id=data.get("id"),
                status=data.get("status", ""),
                created_at=datetime.fromisoformat(data.get("created_at").replace('Z', '+00:00')),
                updated_at=datetime.fromisoformat(data.get("updated_at").replace('Z', '+00:00')),
                client_id=data.get("client_id"),
                grand_total=float(data.get("grand_total", 0)),
                items=items,
                client_name=data.get("client_name"),
                client_phone=data.get("client_phone"),
                delivery_address=data.get("delivery_address"),
                notes=data.get("notes")
            )
            
            return order
            
        except Exception as e:
            logger.error("Failed to parse order response", error=str(e), data=data)
            raise IntegrationError(f"Failed to parse order data: {str(e)}")
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()


# Глобальный экземпляр клиента (ленивая инициализация)
_keycrm_client: Optional[KeyCRMClient] = None


async def get_keycrm_client() -> KeyCRMClient:
    """Получение глобального экземпляра KeyCRM клиента."""
    global _keycrm_client
    
    if _keycrm_client is None:
        _keycrm_client = KeyCRMClient()
    
    return _keycrm_client


async def close_keycrm_client() -> None:
    """Закрытие глобального KeyCRM клиента."""
    global _keycrm_client
    
    if _keycrm_client is not None:
        await _keycrm_client.close()
        _keycrm_client = None