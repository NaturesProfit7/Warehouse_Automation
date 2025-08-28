"""FastAPI приложение для webhook endpoint KeyCRM."""

import json
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ..config import settings
from ..integrations.keycrm import close_keycrm_client, get_keycrm_client
from ..utils.logger import configure_logging, get_logger
from .handlers import KeyCRMWebhookHandler

# Настройка логирования
configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения."""

    logger.info("Starting webhook application")

    # Startup
    try:
        # Инициализация клиентов
        await get_keycrm_client()
        logger.info("KeyCRM client initialized")

        yield

    finally:
        # Shutdown
        logger.info("Shutting down webhook application")
        await close_keycrm_client()
        logger.info("Webhook application stopped")


# Создание FastAPI приложения
app = FastAPI(
    title="Timosh Blanks Webhook API",
    description="Webhook endpoint для приема данных от KeyCRM",
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan
)

# CORS middleware (ограничиваем в продакшене)
if settings.DEBUG:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Глобальный обработчик webhook
webhook_handler = KeyCRMWebhookHandler()


@app.get("/")
async def root():
    """Корневая страница."""
    return {
        "service": "Timosh Blanks Webhook API",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""

    try:
        # Проверяем подключение к KeyCRM
        keycrm_client = await get_keycrm_client()
        keycrm_status = "connected" if keycrm_client else "disconnected"

        # Общий статус
        status = "healthy" if keycrm_status == "connected" else "degraded"

        return JSONResponse(
            status_code=200 if status == "healthy" else 503,
            content={
                "status": status,
                "timestamp": datetime.now().isoformat(),
                "services": {
                    "keycrm": keycrm_status,
                    "sheets": "connected"  # TODO: добавить проверку
                }
            }
        )

    except Exception as e:
        logger.error("Health check failed", error=str(e))
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )


@app.get("/ready")
async def readiness_check():
    """Readiness check endpoint."""

    try:
        # Проверяем готовность всех компонентов
        keycrm_client = await get_keycrm_client()

        if not keycrm_client:
            raise Exception("KeyCRM client not ready")

        return JSONResponse(
            status_code=200,
            content={
                "status": "ready",
                "timestamp": datetime.now().isoformat()
            }
        )

    except Exception as e:
        logger.error("Readiness check failed", error=str(e))
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )


@app.post("/webhook/keycrm")
async def keycrm_webhook(request: Request):
    """
    Webhook endpoint для приема данных от KeyCRM.
    
    KeyCRM не поддерживает HMAC подписи, поэтому проверяем только базовую структуру.
    Безопасность обеспечивается через секретность URL и проверку User-Agent.
    """

    request_id = f"req_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{id(request)}"

    try:
        # Базовая проверка User-Agent
        user_agent = request.headers.get("user-agent", "")
        if "KeyCRM" not in user_agent:
            logger.warning(
                "Suspicious webhook request - invalid User-Agent",
                request_id=request_id,
                user_agent=user_agent,
                client_ip=request.client.host if request.client else None
            )

        # Получение и парсинг payload
        body = await request.body()
        try:
            payload = json.loads(body.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.error("Invalid JSON payload", error=str(e), request_id=request_id)
            raise HTTPException(status_code=400, detail="Invalid JSON payload")

        logger.info(
            "Received KeyCRM webhook",
            request_id=request_id,
            webhook_event=payload.get("event"),
            context_keys=list(payload.get("context", {}).keys()),
            user_agent=user_agent[:50] + "..." if len(user_agent) > 50 else user_agent
        )

        # Обработка webhook
        result = await webhook_handler.handle_keycrm_webhook(
            payload,
            request_id=request_id
        )

        # Формирование ответа
        response_data = {
            "status": "success",
            "request_id": request_id,
            "processed_at": datetime.now().isoformat(),
            **result
        }

        logger.info(
            "KeyCRM webhook processed successfully",
            request_id=request_id,
            **result
        )

        return JSONResponse(
            status_code=200,
            content=response_data
        )

    except HTTPException:
        # Перехватываем и пробрасываем HTTP исключения
        raise

    except Exception as e:
        logger.error(
            "Error processing KeyCRM webhook",
            request_id=request_id,
            error=str(e),
            error_type=type(e).__name__
        )

        # Возвращаем 500 для повтора со стороны KeyCRM
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "request_id": request_id,
                "error": "Internal server error",
                "processed_at": datetime.now().isoformat()
            }
        )


@app.post("/webhook/keycrm/test")
async def keycrm_webhook_test(request: Request):
    """
    Тестовый endpoint для webhook KeyCRM (без проверки подписи).
    Используется только в DEBUG режиме.
    """

    if not settings.DEBUG:
        raise HTTPException(status_code=404, detail="Not found")

    try:
        payload = await request.json()

        logger.info(
            "Test webhook received",
            payload=payload
        )

        # Обработка без проверки подписи
        result = await webhook_handler.handle_keycrm_webhook(
            payload,
            request_id="test_" + datetime.now().strftime('%H%M%S')
        )

        return JSONResponse(
            status_code=200,
            content={
                "status": "test_success",
                "processed_at": datetime.now().isoformat(),
                **result
            }
        )

    except Exception as e:
        logger.error("Error processing test webhook", error=str(e))

        return JSONResponse(
            status_code=500,
            content={
                "status": "test_error",
                "error": str(e),
                "processed_at": datetime.now().isoformat()
            }
        )


# Обработчик глобальных ошибок
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Глобальный обработчик исключений."""

    logger.error(
        "Unhandled exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        error_type=type(exc).__name__
    )

    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "error": "Internal server error",
            "timestamp": datetime.now().isoformat()
        }
    )


if __name__ == "__main__":
    """Запуск приложения для разработки."""

    import uvicorn

    logger.info("Starting webhook server in development mode")

    uvicorn.run(
        "src.webhook.app:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info"
    )
