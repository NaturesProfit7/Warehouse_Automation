"""Валидаторы для бизнес-логики."""

import re
from typing import Dict, Any, Optional
from datetime import datetime

from .models import BlankType, BlankColor, MovementType
from .exceptions import ValidationError


def validate_blank_sku(sku: str) -> bool:
    """Валидация формата SKU заготовки.
    
    Формат: BLK-{TYPE}-{SIZE}-{COLOR}
    Пример: BLK-BONE-25-GLD
    """
    pattern = r"^BLK-(BONE|RING|ROUND|HEART|CLOUD|FLOWER)-(20|25|30)-(GLD|SIL)$"
    return bool(re.match(pattern, sku))


def parse_blank_sku(sku: str) -> Dict[str, str]:
    """Парсинг SKU на компоненты."""
    if not validate_blank_sku(sku):
        raise ValidationError(f"Некорректный формат SKU: {sku}")
    
    parts = sku.split("-")
    return {
        "prefix": parts[0],
        "type": parts[1], 
        "size": parts[2],
        "color": parts[3]
    }


def generate_blank_sku(type: str, size: int, color: str) -> str:
    """Генерация SKU по компонентам."""
    sku = f"BLK-{type}-{size}-{color}"
    
    if not validate_blank_sku(sku):
        raise ValidationError(f"Некорректные компоненты для SKU: {type}, {size}, {color}")
    
    return sku


def validate_movement_qty(qty: int, movement_type: MovementType) -> bool:
    """Валидация количества в движении."""
    if movement_type == MovementType.ORDER and qty >= 0:
        raise ValidationError("Расход по заказу должен быть отрицательным")
    
    if movement_type == MovementType.RECEIPT and qty <= 0:
        raise ValidationError("Приход должен быть положительным")
    
    if abs(qty) > 10000:
        raise ValidationError("Количество не может превышать 10000")
    
    return True


def validate_stock_levels(on_hand: int, min_stock: int, par_stock: int) -> bool:
    """Валидация уровней остатков."""
    if on_hand < 0:
        raise ValidationError("Остаток не может быть отрицательным")
    
    if min_stock <= 0:
        raise ValidationError("Минимальный уровень должен быть положительным")
    
    if par_stock <= min_stock:
        raise ValidationError("Целевой уровень должен быть больше минимального")
    
    return True


def validate_telegram_user_id(user_id: int) -> bool:
    """Валидация Telegram user_id."""
    if user_id <= 0:
        raise ValidationError("User ID должен быть положительным")
    
    if user_id > 999999999999:  # Максимальный ID в Telegram
        raise ValidationError("User ID превышает максимальное значение")
    
    return True


def validate_keycrm_order_data(order_data: Dict[str, Any]) -> bool:
    """Валидация данных заказа из KeyCRM."""
    required_fields = ["id", "status", "items"]
    
    for field in required_fields:
        if field not in order_data:
            raise ValidationError(f"Отсутствует обязательное поле: {field}")
    
    if not isinstance(order_data["items"], list):
        raise ValidationError("Поле 'items' должно быть списком")
    
    if len(order_data["items"]) == 0:
        raise ValidationError("Заказ не содержит товаров")
    
    return True


def validate_mapping_rule(
    product_name: str, 
    size_property: str, 
    metal_color: str, 
    blank_sku: str
) -> bool:
    """Валидация правила маппинга."""
    if not product_name.strip():
        raise ValidationError("Название товара не может быть пустым")
    
    if not size_property.strip():
        raise ValidationError("Размер/свойство не может быть пустым")
    
    if not metal_color.strip():
        raise ValidationError("Цвет металла не может быть пустым")
    
    if not validate_blank_sku(blank_sku):
        raise ValidationError(f"Некорректный SKU заготовки: {blank_sku}")
    
    return True


def validate_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Валидация HMAC подписи вебхука."""
    import hmac
    import hashlib
    
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    # Защищенное сравнение против timing атак
    return hmac.compare_digest(signature, expected_signature)


def sanitize_user_input(text: str, max_length: int = 200) -> str:
    """Очистка пользовательского ввода."""
    if not isinstance(text, str):
        raise ValidationError("Ввод должен быть строкой")
    
    # Удаление лишних пробелов
    text = text.strip()
    
    # Ограничение длины
    if len(text) > max_length:
        text = text[:max_length]
    
    # Удаление опасных символов
    dangerous_chars = ['<', '>', '"', "'", '&', '\0', '\r', '\n']
    for char in dangerous_chars:
        text = text.replace(char, '')
    
    return text


def validate_date_range(
    start_date: Optional[datetime], 
    end_date: Optional[datetime]
) -> bool:
    """Валидация диапазона дат."""
    if start_date and end_date:
        if start_date >= end_date:
            raise ValidationError("Начальная дата должна быть меньше конечной")
    
    if start_date and start_date > datetime.now():
        raise ValidationError("Начальная дата не может быть в будущем")
    
    return True