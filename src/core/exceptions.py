"""Кастомные исключения для системы."""


class TimoshBlanksError(Exception):
    """Базовое исключение для всех ошибок системы."""
    
    def __init__(self, message: str, details: dict = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class ConfigurationError(TimoshBlanksError):
    """Ошибка конфигурации."""
    pass


class IntegrationError(TimoshBlanksError):
    """Ошибка интеграции с внешними сервисами."""
    pass


class KeyCRMError(IntegrationError):
    """Ошибка при работе с KeyCRM API."""
    pass


class GoogleSheetsError(IntegrationError):
    """Ошибка при работе с Google Sheets."""
    pass


class TelegramBotError(IntegrationError):
    """Ошибка Telegram бота."""
    pass


class ValidationError(TimoshBlanksError):
    """Ошибка валидации данных."""
    pass


class MappingError(TimoshBlanksError):
    """Ошибка маппинга товаров."""
    pass


class StockCalculationError(TimoshBlanksError):
    """Ошибка расчета остатков."""
    pass


class WebhookAuthError(TimoshBlanksError):
    """Ошибка авторизации вебхука."""
    pass


class DuplicateMovementError(TimoshBlanksError):
    """Дубликат движения товара."""
    pass


class InsufficientStockError(TimoshBlanksError):
    """Недостаточно товара на складе."""
    pass


class RetryableError(TimoshBlanksError):
    """Ошибка, которую можно повторить."""
    pass


class NonRetryableError(TimoshBlanksError):
    """Критическая ошибка, которую нельзя повторять."""
    pass