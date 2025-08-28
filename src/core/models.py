from datetime import date, datetime
from enum import Enum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, computed_field


class BlankType(str, Enum):
    """Типы заготовок."""
    BONE = "BONE"
    RING = "RING"
    ROUND = "ROUND"
    HEART = "HEART"
    CLOUD = "CLOUD"
    FLOWER = "FLOWER"


class BlankColor(str, Enum):
    """Цвета заготовок."""
    GOLD = "GLD"
    SILVER = "SIL"


class MovementType(str, Enum):
    """Типы движений товара."""
    ORDER = "order"          # Расход по заказу
    RECEIPT = "receipt"      # Приход товара
    CORRECTION = "correction" # Корректировка остатков
    SCRAP = "scrap"          # Списание брака


class MovementSourceType(str, Enum):
    """Источники движений."""
    KEYCRM_WEBHOOK = "keycrm_webhook"
    TELEGRAM = "telegram"
    MANUAL = "manual"


class UrgencyLevel(str, Enum):
    """Уровни приоритета закупок."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class BlankSKU(BaseModel):
    """Модель заготовки с базовыми атрибутами."""

    blank_sku: str = Field(..., description="Уникальный код заготовки")
    type: BlankType = Field(..., description="Тип заготовки")
    size_mm: int = Field(..., description="Размер в мм")
    color: BlankColor = Field(..., description="Цвет")
    name_ua: str = Field(..., description="Название на украинском")
    active: bool = Field(default=True, description="Активность SKU")

    @computed_field
    @property
    def display_name(self) -> str:
        """Читаемое название для UI."""
        return f"{self.name_ua} {self.size_mm}мм {self.color.value}"


class MasterBlank(BlankSKU):
    """Справочник заготовок с параметрами планирования."""

    opening_stock: int = Field(default=0, description="Начальный остаток")
    min_stock: int = Field(default=100, description="Минимальный уровень")
    par_stock: int = Field(default=300, description="Целевой уровень")
    notes: str | None = Field(default=None, description="Примечания")


class ProductMapping(BaseModel):
    """Правила маппинга товаров KeyCRM → заготовки."""

    product_name: str = Field(..., description="Название в KeyCRM (укр.)")
    size_property: str = Field(..., description="Размер/свойство (укр.)")
    metal_color: str = Field(..., description="Цвет металла (укр.)")
    blank_sku: str = Field(..., description="Код заготовки")
    qty_per_unit: int = Field(default=1, description="Количество на единицу")
    active: bool = Field(default=True, description="Активность правила")
    priority: int = Field(default=50, description="Приоритет (1-100)")
    created_at: datetime = Field(default_factory=datetime.now)


class Movement(BaseModel):
    """Движение товара по складу."""

    id: UUID = Field(default_factory=uuid4, description="UUID движения")
    timestamp: datetime = Field(default_factory=datetime.now, description="Время операции")
    type: MovementType = Field(..., description="Тип движения")
    source_type: MovementSourceType = Field(..., description="Источник движения")
    source_id: str = Field(..., description="ID источника")
    blank_sku: str = Field(..., description="Код заготовки")
    qty: int = Field(..., description="Количество (+/-)")
    balance_after: int = Field(..., description="Остаток после операции")
    user: str | None = Field(default=None, description="Пользователь")
    note: str | None = Field(default=None, description="Примечание")
    hash: str = Field(..., description="SHA256 для дедупликации")

    model_config = {
        "json_encoders": {
            UUID: str,
            datetime: lambda v: v.isoformat()
        }
    }


class CurrentStock(BaseModel):
    """Текущие остатки заготовок."""

    blank_sku: str = Field(..., description="Код заготовки")
    on_hand: int = Field(..., description="Текущий остаток")
    reserved: int = Field(default=0, description="Зарезервировано")
    available: int = Field(..., description="Доступно")
    last_receipt_date: date | None = Field(default=None, description="Последний приход")
    last_order_date: date | None = Field(default=None, description="Последний расход")
    avg_daily_usage: float = Field(default=0.0, description="Средний расход/день")
    days_of_stock: int | None = Field(default=None, description="Дней до исчерпания")
    last_updated: datetime = Field(default_factory=datetime.now)


class ReplenishmentRecommendation(BaseModel):
    """Рекомендация по закупке."""

    blank_sku: str = Field(..., description="Код заготовки")
    on_hand: int = Field(..., description="Текущий остаток")
    min_level: int = Field(..., description="Минимальный уровень")
    reorder_point: int = Field(..., description="Точка заказа")
    target_level: int = Field(..., description="Целевой уровень")
    need_order: bool = Field(..., description="Требуется заказ")
    recommended_qty: int = Field(..., description="Рекомендуемое количество")
    urgency: UrgencyLevel = Field(..., description="Приоритет")
    estimated_stockout: date | None = Field(default=None, description="Прогноз исчерпания")
    last_calculated: datetime = Field(default_factory=datetime.now)


class UnmappedItem(BaseModel):
    """Позиция без маппинга."""

    timestamp: datetime = Field(default_factory=datetime.now, description="Время обнаружения")
    order_id: str = Field(..., description="ID заказа KeyCRM")
    line_id: str = Field(..., description="ID строки заказа")
    product_name: str = Field(..., description="Название товара")
    properties: dict[str, Any] = Field(default_factory=dict, description="Свойства товара")
    suggested_sku: str | None = Field(default=None, description="Предполагаемый SKU")
    error_type: str = Field(..., description="Тип ошибки")
    resolution: str = Field(default="pending", description="Статус решения")


class AuditLog(BaseModel):
    """Запись журнала аудита."""

    timestamp: datetime = Field(default_factory=datetime.now)
    user_id: str = Field(..., description="ID пользователя")
    user_name: str | None = Field(default=None, description="Имя пользователя")
    action: str = Field(..., description="Тип действия")
    entity: str = Field(..., description="Объект действия")
    entity_id: str = Field(..., description="ID объекта")
    old_value: dict[str, Any] | None = Field(default=None, description="Старое значение")
    new_value: dict[str, Any] | None = Field(default=None, description="Новое значение")
    source: str = Field(..., description="Источник (telegram/sheets/webhook/system)")
    ip_address: str | None = Field(default=None, description="IP адрес")
    result: Literal["success", "failure"] = Field(..., description="Результат")
    error_message: str | None = Field(default=None, description="Сообщение об ошибке")


class KeyCRMWebhookPayload(BaseModel):
    """Payload вебхука от KeyCRM."""

    event: str = Field(..., description="Тип события")
    context: dict[str, Any] = Field(..., description="Контекст события")

    @computed_field
    @property
    def order_id(self) -> int | None:
        """Извлечение ID заказа из контекста."""
        return self.context.get("id")

    @computed_field
    @property
    def order_status(self) -> str | None:
        """Извлечение статуса заказа из контекста."""
        return self.context.get("status")
