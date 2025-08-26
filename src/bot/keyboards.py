"""Клавиатуры для Telegram бота."""

from typing import List, Optional

from aiogram.types import (
    InlineKeyboardMarkup, 
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton
)

from ..core.models import BlankType, BlankColor


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню бота."""
    
    buttons = [
        [
            InlineKeyboardButton(text="➕ Приход", callback_data="receipt"),
            InlineKeyboardButton(text="📦 Остатки", callback_data="stock")
        ],
        [
            InlineKeyboardButton(text="📊 Отчет", callback_data="report"),
            InlineKeyboardButton(text="⚙️ Коррекция", callback_data="correction")
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для отмены операции."""
    
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
        ]]
    )


def get_blank_type_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора типа заготовки."""
    
    buttons = [
        [InlineKeyboardButton(text="🦴 Кістка", callback_data="type_BONE")],
        [InlineKeyboardButton(text="🟢 Бублик", callback_data="type_RING")],
        [InlineKeyboardButton(text="⚪ Круглий", callback_data="type_ROUND")],
        [InlineKeyboardButton(text="❤️ Фігурний", callback_data="type_SHAPED")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_bone_size_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора размера кости."""
    
    buttons = [
        [InlineKeyboardButton(text="25 мм (маленька)", callback_data="size_25")],
        [InlineKeyboardButton(text="30 мм (велика)", callback_data="size_30")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_type")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_ring_size_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора размера бублика."""
    
    buttons = [
        [InlineKeyboardButton(text="25 мм", callback_data="size_25")],
        [InlineKeyboardButton(text="30 мм", callback_data="size_30")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_type")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_round_size_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора размера круглого."""
    
    buttons = [
        [InlineKeyboardButton(text="20 мм", callback_data="size_20")],
        [InlineKeyboardButton(text="25 мм", callback_data="size_25")],
        [InlineKeyboardButton(text="30 мм", callback_data="size_30")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_type")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_shaped_form_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора формы фигурного."""
    
    buttons = [
        [InlineKeyboardButton(text="❤️ Серце", callback_data="shape_HEART")],
        [InlineKeyboardButton(text="🌸 Квітка", callback_data="shape_FLOWER")],
        [InlineKeyboardButton(text="☁️ Хмарка", callback_data="shape_CLOUD")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_type")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_color_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора цвета."""
    
    buttons = [
        [
            InlineKeyboardButton(text="🟡 Золото", callback_data="color_GLD"),
            InlineKeyboardButton(text="⚪ Срібло", callback_data="color_SIL")
        ],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_size")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_confirmation_keyboard(large_quantity: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура для подтверждения операции."""
    
    text_prefix = "⚠️ " if large_quantity else ""
    
    buttons = [
        [
            InlineKeyboardButton(text="✅ Так", callback_data="confirm_yes"),
            InlineKeyboardButton(text="❌ Ні", callback_data="confirm_no")
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_report_type_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора типа отчета."""
    
    buttons = [
        [InlineKeyboardButton(text="📋 Короткий звіт", callback_data="report_short")],
        [InlineKeyboardButton(text="📄 Повний звіт", callback_data="report_full")],
        [InlineKeyboardButton(text="🔴 Критичні позиції", callback_data="report_critical")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_correction_type_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора типа корректировки."""
    
    buttons = [
        [InlineKeyboardButton(text="➕ Додати", callback_data="correction_add")],
        [InlineKeyboardButton(text="➖ Вирахувати", callback_data="correction_subtract")],
        [InlineKeyboardButton(text="🔄 Встановити точно", callback_data="correction_set")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_sku_selection_keyboard(skus: List[str]) -> InlineKeyboardMarkup:
    """Клавиатура для выбора SKU из списка."""
    
    buttons = []
    
    # Группируем по типам для удобства
    types_order = ["BONE", "RING", "ROUND", "HEART", "FLOWER", "CLOUD"]
    grouped_skus = {}
    
    for sku in skus:
        sku_type = sku.split('-')[1]
        if sku_type not in grouped_skus:
            grouped_skus[sku_type] = []
        grouped_skus[sku_type].append(sku)
    
    # Добавляем кнопки в порядке типов
    for sku_type in types_order:
        if sku_type in grouped_skus:
            for sku in sorted(grouped_skus[sku_type]):
                # Красивое отображение SKU
                display_name = _format_sku_for_display(sku)
                buttons.append([InlineKeyboardButton(
                    text=display_name, 
                    callback_data=f"sku_{sku}"
                )])
    
    # Добавляем кнопки управления
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _format_sku_for_display(sku: str) -> str:
    """Форматирование SKU для красивого отображения."""
    
    parts = sku.split('-')
    if len(parts) != 4:
        return sku
        
    _, sku_type, size, color = parts
    
    # Маппинг типов
    type_mapping = {
        "BONE": "🦴 Кістка",
        "RING": "🟢 Бублик", 
        "ROUND": "⚪ Круглий",
        "HEART": "❤️ Серце",
        "FLOWER": "🌸 Квітка",
        "CLOUD": "☁️ Хмарка"
    }
    
    # Маппинг цветов
    color_mapping = {
        "GLD": "🟡",
        "SIL": "⚪"
    }
    
    type_display = type_mapping.get(sku_type, sku_type)
    color_display = color_mapping.get(color, color)
    
    return f"{type_display} {size}мм {color_display}"


def get_back_keyboard() -> InlineKeyboardMarkup:
    """Простая клавиатура с кнопкой назад."""
    
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="↩️ Назад", callback_data="back"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
        ]]
    )