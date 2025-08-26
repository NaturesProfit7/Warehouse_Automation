"""Аутентификация и авторизация webhook запросов."""

import json
from typing import Dict, Any

from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer

from ..integrations.keycrm import get_keycrm_client
from ..core.exceptions import WebhookAuthError
from ..utils.logger import get_logger

logger = get_logger(__name__)

# HTTP Bearer схема для документации
security = HTTPBearer(auto_error=False)


async def verify_webhook_signature(
    request: Request,
    authorization = Depends(security)
) -> Dict[str, Any]:
    """
    Проверка HMAC подписи KeyCRM webhook.
    
    Args:
        request: HTTP запрос
        authorization: Bearer токен (необязательный)
        
    Returns:
        Dict[str, Any]: Валидированный payload
        
    Raises:
        HTTPException: При ошибке аутентификации
    """
    
    try:
        # Получение заголовка с подписью
        signature_header = request.headers.get("X-KeyCRM-Signature")
        if not signature_header:
            # Проверяем альтернативные заголовки
            signature_header = request.headers.get("X-Signature")
            
        if not signature_header:
            logger.warning(
                "Missing signature header",
                headers=dict(request.headers),
                url=str(request.url)
            )
            raise HTTPException(
                status_code=401,
                detail="Missing signature header"
            )
        
        # Получение тела запроса
        body = await request.body()
        if not body:
            logger.warning("Empty request body")
            raise HTTPException(
                status_code=400,
                detail="Empty request body"
            )
        
        # Проверка подписи через KeyCRM клиент
        keycrm_client = await get_keycrm_client()
        is_valid = keycrm_client.verify_webhook_signature(body, signature_header)
        
        if not is_valid:
            logger.warning(
                "Invalid webhook signature",
                signature=signature_header[:20] + "..." if len(signature_header) > 20 else signature_header,
                body_size=len(body),
                content_type=request.headers.get("Content-Type")
            )
            raise HTTPException(
                status_code=403,
                detail="Invalid signature"
            )
        
        # Парсинг JSON payload
        try:
            payload = json.loads(body.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.error(
                "Failed to parse JSON payload",
                error=str(e),
                body_preview=body[:200].decode('utf-8', errors='replace')
            )
            raise HTTPException(
                status_code=400,
                detail="Invalid JSON payload"
            )
        
        # Базовая валидация структуры
        if not isinstance(payload, dict):
            logger.error("Payload is not a dictionary", payload_type=type(payload))
            raise HTTPException(
                status_code=400,
                detail="Payload must be a JSON object"
            )
        
        if "event" not in payload:
            logger.error("Missing event field in payload", payload_keys=list(payload.keys()))
            raise HTTPException(
                status_code=400,
                detail="Missing 'event' field in payload"
            )
        
        logger.debug(
            "Webhook signature verified successfully",
            event=payload.get("event"),
            payload_size=len(body)
        )
        
        return payload
        
    except HTTPException:
        # Пробрасываем HTTP исключения как есть
        raise
        
    except Exception as e:
        logger.error(
            "Unexpected error during signature verification",
            error=str(e),
            error_type=type(e).__name__
        )
        raise HTTPException(
            status_code=500,
            detail="Internal server error during authentication"
        )


async def get_request_info(request: Request) -> Dict[str, Any]:
    """
    Извлечение информации о запросе для логирования.
    
    Args:
        request: HTTP запрос
        
    Returns:
        Dict[str, Any]: Информация о запросе
    """
    
    return {
        "method": request.method,
        "url": str(request.url),
        "client_ip": request.client.host if request.client else None,
        "user_agent": request.headers.get("User-Agent"),
        "content_type": request.headers.get("Content-Type"),
        "content_length": request.headers.get("Content-Length"),
        "timestamp": request.state.__dict__.get("start_time")
    }


def validate_keycrm_event(payload: Dict[str, Any]) -> bool:
    """
    Валидация события KeyCRM.
    
    Args:
        payload: Payload вебхука
        
    Returns:
        bool: True если событие валидное
    """
    
    event = payload.get("event", "")
    context = payload.get("context", {})
    
    # Проверяем что это событие изменения статуса заказа
    if event != "order.change_order_status":
        logger.debug(
            "Skipping non-order event",
            event=event
        )
        return False
    
    # Проверяем что статус изменился на confirmed
    new_status = context.get("status", "")
    if new_status != "confirmed":
        logger.debug(
            "Skipping non-confirmed status",
            status=new_status,
            order_id=context.get("id")
        )
        return False
    
    # Проверяем наличие order ID
    order_id = context.get("id")
    if not order_id:
        logger.warning(
            "Missing order ID in context",
            context=context
        )
        return False
    
    return True


class WebhookRateLimiter:
    """Простой rate limiter для webhook запросов."""
    
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests = {}  # IP -> список timestamps
    
    def is_allowed(self, client_ip: str) -> bool:
        """
        Проверка допустимости запроса.
        
        Args:
            client_ip: IP клиента
            
        Returns:
            bool: True если запрос допустим
        """
        
        import time
        
        now = time.time()
        
        # Инициализируем список для IP если его нет
        if client_ip not in self._requests:
            self._requests[client_ip] = []
        
        # Удаляем старые запросы
        self._requests[client_ip] = [
            timestamp for timestamp in self._requests[client_ip]
            if now - timestamp < self.window_seconds
        ]
        
        # Проверяем лимит
        if len(self._requests[client_ip]) >= self.max_requests:
            logger.warning(
                "Rate limit exceeded",
                client_ip=client_ip,
                requests_count=len(self._requests[client_ip]),
                limit=self.max_requests
            )
            return False
        
        # Добавляем текущий запрос
        self._requests[client_ip].append(now)
        return True


# Глобальный экземпляр rate limiter
rate_limiter = WebhookRateLimiter()


async def check_rate_limit(request: Request):
    """
    Middleware для проверки rate limit.
    
    Args:
        request: HTTP запрос
        
    Raises:
        HTTPException: При превышении лимита
    """
    
    client_ip = request.client.host if request.client else "unknown"
    
    if not rate_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Too Many Requests"
        )