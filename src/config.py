from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Конфигурация приложения согласно ТЗ."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    # KeyCRM интеграция
    KEYCRM_API_TOKEN: str = Field(..., description="API токен KeyCRM")
    KEYCRM_API_URL: str = Field(
        default="https://api.keycrm.app", description="Base URL KeyCRM API"
    )
    KEYCRM_WEBHOOK_SECRET: str = Field(
        ..., description="Секретный ключ для проверки HMAC подписи вебхуков"
    )

    # Google Sheets интеграция
    GSHEETS_ID: str = Field(..., description="ID Google Sheets книги")
    GOOGLE_CREDENTIALS_JSON: str = Field(
        ..., description="Service Account credentials в формате JSON"
    )

    # Telegram бот
    TELEGRAM_BOT_TOKEN: str = Field(..., description="Токен Telegram бота")
    TELEGRAM_CHAT_ID: str = Field(..., description="ID чата для уведомлений")
    TELEGRAM_ALLOWED_USERS: List[int] = Field(
        default=[7373293370], description="Список user_id с доступом к боту"
    )
    TELEGRAM_ADMIN_USERS: List[int] = Field(
        default=[7373293370], description="Список admin user_id"
    )

    # Webhook endpoint
    WEBHOOK_ENDPOINT: str = Field(
        default="https://blanks.timosh-design.com/webhook/keycrm",
        description="Endpoint для приема вебхуков"
    )

    # Параметры планирования (простой режим)
    LEAD_TIME_DAYS: int = Field(
        default=14, description="Срок поставки заготовок в днях"
    )
    SCRAP_PCT: float = Field(default=0.05, description="Процент брака (5%)")
    TARGET_COVER_DAYS: int = Field(
        default=14, description="Дополнительная подушка безопасности в днях"
    )
    MIN_STOCK_DEFAULT: int = Field(
        default=100, description="Минимальный остаток по умолчанию"
    )
    PAR_STOCK_DEFAULT: int = Field(
        default=300, description="Целевой остаток по умолчанию"
    )

    # Режим расчета (простой для MVP)
    USE_DEMAND_METRICS: bool = Field(
        default=False, description="Использовать динамический расчет по спросу"
    )

    # Расписание
    TIMEZONE: str = Field(default="Europe/Kyiv", description="Часовой пояс")
    DAILY_REPORT_TIME: str = Field(
        default="20:00", description="Время ежедневного расчета"
    )
    DAILY_SYNC_TIME: str = Field(
        default="02:00", description="Время ежедневной сверки данных"
    )

    # Технические параметры
    BATCH_SIZE: int = Field(default=100, description="Размер батча для Sheets API")
    MAX_RETRIES: int = Field(default=3, description="Максимум попыток при ошибках")
    RETRY_DELAY_SECONDS: int = Field(
        default=1, description="Начальная задержка retry в секундах"
    )

    # Логирование
    LOG_LEVEL: str = Field(default="INFO", description="Уровень логирования")
    LOG_FORMAT: str = Field(default="json", description="Формат логов")

    # Debug режим
    DEBUG: bool = Field(default=False, description="Режим отладки")


# Глобальный экземпляр настроек (ленивая загрузка)
def get_settings() -> Settings:
    """Получение настроек."""
    return Settings()

# Для обратной совместимости - создаем только при доступе к атрибуту
class LazySettings:
    _instance = None
    
    def __getattr__(self, name):
        if self._instance is None:
            self._instance = Settings()
        return getattr(self._instance, name)

settings = LazySettings()