"""Обработчики команд и сообщений Telegram бота."""

import asyncio
from typing import Dict, Any

from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from .keyboards import (
    get_main_menu_keyboard,
    get_cancel_keyboard,
    get_blank_type_keyboard,
    get_bone_size_keyboard,
    get_ring_size_keyboard,
    get_round_size_keyboard,
    get_shaped_form_keyboard,
    get_color_keyboard,
    get_confirmation_keyboard,
    get_report_type_keyboard,
    get_correction_type_keyboard,
    get_sku_selection_keyboard,
    _format_sku_for_display
)
from .states import ReceiptStates, CorrectionStates, ReportStates
from ..utils.logger import get_logger

logger = get_logger(__name__)

# Создаем роутер для обработчиков
router = Router()


# === ОСНОВНЫЕ КОМАНДЫ ===

@router.message(Command("start"))
async def cmd_start(message: Message, user_info: Dict[str, Any]) -> None:
    """Обработчик команды /start."""
    
    user_name = user_info.get("full_name", "Користувач")
    
    welcome_text = (
        f"🏭 <b>Привіт, {user_name}!</b>\n\n"
        f"Я допоможу тобі керувати залишками заготовок для адресників.\n\n"
        f"📋 <b>Доступні функції:</b>\n"
        f"• ➕ <b>Приход</b> — додавання нових заготовок\n"
        f"• 📦 <b>Остатки</b> — перегляд поточних залишків\n"
        f"• 📊 <b>Отчет</b> — звіти по складу\n"
        f"• ⚙️ <b>Коррекция</b> — виправлення залишків\n\n"
        f"Оберіть дію:"
    )
    
    await message.answer(
        welcome_text, 
        reply_markup=get_main_menu_keyboard(),
        parse_mode="HTML"
    )
    
    logger.info("Start command executed", user_id=user_info.get("id"))


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Обработчик команды /help."""
    
    help_text = (
        "🆘 <b>Довідка по командам</b>\n\n"
        "📋 <b>Основні команди:</b>\n"
        "• /start — головне меню\n"
        "• /receipt — швидкий додаток приходу\n"
        "• /report — швидкий звіт по залишках\n"
        "• /cancel — скасувати поточну операцію\n"
        "• /help — ця довідка\n\n"
        "⚙️ <b>Адміністратори:</b>\n"
        "• /correction <SKU> <КІЛЬКІСТЬ> — швидка корекція\n\n"
        "❓ <b>Потрібна допомога?</b>\n"
        "Зверніться до адміністратора"
    )
    
    await message.answer(help_text, parse_mode="HTML")


@router.message(Command("cancel"))
@router.callback_query(F.data == "cancel")
async def cancel_operation(update, state: FSMContext) -> None:
    """Отмена текущей операции."""
    
    await state.clear()
    
    if isinstance(update, Message):
        await update.answer(
            "❌ Операцію скасовано",
            reply_markup=get_main_menu_keyboard()
        )
    else:  # CallbackQuery
        await update.message.edit_text(
            "❌ Операцію скасовано",
            reply_markup=get_main_menu_keyboard()
        )
        await update.answer()


# === ГЛАВНОЕ МЕНЮ ===

@router.callback_query(F.data == "main_menu")
async def show_main_menu(callback: CallbackQuery) -> None:
    """Показ главного меню."""
    
    await callback.message.edit_text(
        "🏭 <b>Головне меню</b>\n\nОберіть дію:",
        reply_markup=get_main_menu_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


# === ПРИХОД ЗАГОТОВОК ===

@router.message(Command("receipt"))
@router.callback_query(F.data == "receipt")
async def start_receipt(update, state: FSMContext) -> None:
    """Начало процесса добавления прихода."""
    
    await state.set_state(ReceiptStates.waiting_for_type)
    
    text = (
        "➕ <b>Додавання приходу заготовок</b>\n\n"
        "Оберіть тип заготовки:"
    )
    
    if isinstance(update, Message):
        await update.answer(text, reply_markup=get_blank_type_keyboard(), parse_mode="HTML")
    else:  # CallbackQuery
        await update.message.edit_text(
            text, 
            reply_markup=get_blank_type_keyboard(),
            parse_mode="HTML"
        )
        await update.answer()


@router.callback_query(ReceiptStates.waiting_for_type, F.data.startswith("type_"))
async def process_blank_type(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработка выбора типа заготовки."""
    
    blank_type = callback.data[5:]  # Убираем "type_"
    await state.update_data(blank_type=blank_type)
    
    if blank_type == "BONE":
        keyboard = get_bone_size_keyboard()
        text = "🦴 <b>Кістка</b>\n\nОберіть розмір:"
    elif blank_type == "RING":
        keyboard = get_ring_size_keyboard()
        text = "🟢 <b>Бублик</b>\n\nОберіть розмір:"
    elif blank_type == "ROUND":
        keyboard = get_round_size_keyboard()
        text = "⚪ <b>Круглий</b>\n\nОберіть розмір:"
    elif blank_type == "SHAPED":
        keyboard = get_shaped_form_keyboard()
        text = "❤️ <b>Фігурний</b>\n\nОберіть форму:"
    else:
        await callback.answer("❌ Невідомий тип заготовки")
        return
    
    await state.set_state(ReceiptStates.waiting_for_size)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(ReceiptStates.waiting_for_size, F.data.startswith("size_"))
async def process_blank_size(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработка выбора размера заготовки."""
    
    size = callback.data[5:]  # Убираем "size_"
    await state.update_data(size=size)
    await state.set_state(ReceiptStates.waiting_for_color)
    
    text = f"📏 <b>Розмір: {size} мм</b>\n\nОберіть колір металу:"
    
    await callback.message.edit_text(
        text, 
        reply_markup=get_color_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(ReceiptStates.waiting_for_size, F.data.startswith("shape_"))
async def process_blank_shape(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработка выбора формы фигурной заготовки."""
    
    shape = callback.data[6:]  # Убираем "shape_"
    # Для фигурных заготовок размер всегда 25мм
    await state.update_data(shape=shape, size="25")
    await state.set_state(ReceiptStates.waiting_for_color)
    
    shape_names = {
        "HEART": "❤️ Серце",
        "FLOWER": "🌸 Квітка", 
        "CLOUD": "☁️ Хмарка"
    }
    
    shape_name = shape_names.get(shape, shape)
    text = f"{shape_name}\n\nОберіть колір металу:"
    
    await callback.message.edit_text(
        text, 
        reply_markup=get_color_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(ReceiptStates.waiting_for_color, F.data.startswith("color_"))
async def process_blank_color(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработка выбора цвета заготовки."""
    
    color = callback.data[6:]  # Убираем "color_"
    await state.update_data(color=color)
    await state.set_state(ReceiptStates.waiting_for_quantity)
    
    # Формируем SKU для отображения
    data = await state.get_data()
    sku = _build_sku_from_data(data)
    
    color_names = {"GLD": "🟡 Золото", "SIL": "⚪ Срібло"}
    color_name = color_names.get(color, color)
    
    text = (
        f"{color_name}\n\n"
        f"🏷️ <b>SKU:</b> <code>{sku}</code>\n\n"
        f"Введіть кількість заготовок:"
    )
    
    await callback.message.edit_text(text, reply_markup=get_cancel_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.message(ReceiptStates.waiting_for_quantity)
async def process_quantity_input(message: Message, state: FSMContext) -> None:
    """Обработка ввода количества."""
    
    try:
        quantity = int(message.text.strip())
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        
    except ValueError:
        await message.answer(
            "❌ Невірне значення!\n"
            "Введіть ціле позитивне число:",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    await state.update_data(quantity=quantity)
    
    # Если количество больше 100, требуем подтверждения
    if quantity > 100:
        await state.set_state(ReceiptStates.waiting_for_confirmation)
        
        data = await state.get_data()
        sku = _build_sku_from_data(data)
        
        text = (
            f"⚠️ <b>Велика партія!</b>\n\n"
            f"🏷️ <b>SKU:</b> <code>{sku}</code>\n"
            f"📦 <b>Кількість:</b> {quantity} шт\n\n"
            f"Підтвердіть додавання приходу:"
        )
        
        await message.answer(
            text, 
            reply_markup=get_confirmation_keyboard(large_quantity=True),
            parse_mode="HTML"
        )
    else:
        # Сразу сохраняем
        await _save_receipt(message, state)


@router.callback_query(ReceiptStates.waiting_for_confirmation, F.data == "confirm_yes")
async def confirm_receipt(callback: CallbackQuery, state: FSMContext) -> None:
    """Подтверждение добавления прихода."""
    
    await _save_receipt(callback.message, state, is_callback=True)
    await callback.answer()


@router.callback_query(ReceiptStates.waiting_for_confirmation, F.data == "confirm_no")
async def decline_receipt(callback: CallbackQuery, state: FSMContext) -> None:
    """Отклонение добавления прихода."""
    
    await state.set_state(ReceiptStates.waiting_for_quantity)
    
    await callback.message.edit_text(
        "❌ Операцію скасовано\n\n"
        "Введіть нову кількість або натисніть /cancel:",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()


# === ОТЧЕТЫ ===

@router.message(Command("report"))
@router.callback_query(F.data == "report")
async def show_report_menu(update) -> None:
    """Показ меню отчетов."""
    
    text = "📊 <b>Звіти по складу</b>\n\nОберіть тип звіту:"
    
    if isinstance(update, Message):
        await update.answer(text, reply_markup=get_report_type_keyboard(), parse_mode="HTML")
    else:  # CallbackQuery
        await update.message.edit_text(
            text, 
            reply_markup=get_report_type_keyboard(),
            parse_mode="HTML"
        )
        await update.answer()


@router.callback_query(F.data.startswith("report_"))
async def process_report_type(callback: CallbackQuery) -> None:
    """Обработка выбора типа отчета."""
    
    report_type = callback.data[7:]  # Убираем "report_"
    
    # Здесь будет интеграция с сервисом отчетов
    # Пока показываем заглушку
    
    reports = {
        "short": "📋 <b>Короткий звіт</b>\n\n🔄 Завантаження...",
        "full": "📄 <b>Повний звіт</b>\n\n🔄 Завантаження...",
        "critical": "🔴 <b>Критичні позиції</b>\n\n🔄 Завантаження..."
    }
    
    text = reports.get(report_type, "❌ Невідомий тип звіту")
    
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()
    
    # Эмуляция загрузки отчета
    await asyncio.sleep(1)
    
    # Заглушка отчета
    mock_report = _generate_mock_report(report_type)
    
    await callback.message.edit_text(
        mock_report, 
        reply_markup=get_main_menu_keyboard(),
        parse_mode="HTML"
    )


# === КОРРЕКТИРОВКИ (ТОЛЬКО ДЛЯ АДМИНИСТРАТОРОВ) ===

@router.callback_query(F.data == "correction")
async def start_correction(callback: CallbackQuery, is_admin: bool) -> None:
    """Начало процесса корректировки."""
    
    if not is_admin:
        await callback.answer("❌ Недостатньо прав доступу", show_alert=True)
        return
    
    text = "⚙️ <b>Корекція залишків</b>\n\nОберіть тип операції:"
    
    await callback.message.edit_text(
        text, 
        reply_markup=get_correction_type_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


# === НАВИГАЦИЯ ===

@router.callback_query(F.data == "back_to_type")
async def back_to_type_selection(callback: CallbackQuery, state: FSMContext) -> None:
    """Возврат к выбору типа заготовки."""
    
    await state.set_state(ReceiptStates.waiting_for_type)
    
    text = "➕ <b>Додавання приходу заготовок</b>\n\nОберіть тип заготовки:"
    
    await callback.message.edit_text(
        text, 
        reply_markup=get_blank_type_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_size")
async def back_to_size_selection(callback: CallbackQuery, state: FSMContext) -> None:
    """Возврат к выбору размера."""
    
    data = await state.get_data()
    blank_type = data.get("blank_type")
    
    await state.set_state(ReceiptStates.waiting_for_size)
    
    if blank_type == "BONE":
        keyboard = get_bone_size_keyboard()
        text = "🦴 <b>Кістка</b>\n\nОберіть розмір:"
    elif blank_type == "RING":
        keyboard = get_ring_size_keyboard()
        text = "🟢 <b>Бублик</b>\n\nОберіть розмір:"
    elif blank_type == "ROUND":
        keyboard = get_round_size_keyboard()
        text = "⚪ <b>Круглий</b>\n\nОберіть розмір:"
    elif blank_type == "SHAPED":
        keyboard = get_shaped_form_keyboard()
        text = "❤️ <b>Фігурний</b>\n\nОберіть форму:"
    else:
        # Fallback
        await back_to_type_selection(callback, state)
        return
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===

def _build_sku_from_data(data: Dict[str, Any]) -> str:
    """Построение SKU из данных состояния."""
    
    blank_type = data.get("blank_type", "")
    size = data.get("size", "")
    color = data.get("color", "")
    shape = data.get("shape", "")
    
    # Для фигурных заготовок используем форму как тип
    if blank_type == "SHAPED" and shape:
        sku_type = shape
    else:
        sku_type = blank_type
    
    return f"BLK-{sku_type}-{size}-{color}"


async def _save_receipt(message: Message, state: FSMContext, is_callback: bool = False) -> None:
    """Сохранение прихода заготовки."""
    
    data = await state.get_data()
    sku = _build_sku_from_data(data)
    quantity = data.get("quantity", 0)
    
    # Здесь будет интеграция с сервисом управления остатками
    # Пока показываем успешное сохранение
    
    logger.info(
        "Receipt added",
        sku=sku,
        quantity=quantity,
        user_id=message.from_user.id if message else None
    )
    
    text = (
        f"✅ <b>Приход успішно додано!</b>\n\n"
        f"🏷️ <b>SKU:</b> <code>{sku}</code>\n"
        f"📦 <b>Кількість:</b> +{quantity} шт\n"
        f"📊 <b>Залишок:</b> ??? шт\n\n"  # Здесь будет реальный остаток
        f"Операцію збережено в систему."
    )
    
    keyboard = get_main_menu_keyboard()
    
    if is_callback:
        await message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    
    await state.clear()


def _generate_mock_report(report_type: str) -> str:
    """Генерация заглушки отчета."""
    
    if report_type == "short":
        return (
            "📋 <b>Короткий звіт</b>\n"
            "🗓️ 26.08.2025 20:00\n\n"
            "🔴 <b>Критично низький рівень (2):</b>\n"
            "• BLK-HEART-25-SIL: 45 шт\n"
            "• BLK-RING-30-GLD: 30 шт\n\n"
            "🟡 <b>Потребують уваги (3):</b>\n"
            "• BLK-ROUND-25-SIL: 112 шт\n"
            "• BLK-BONE-30-GLD: 108 шт\n"
            "• BLK-CLOUD-25-SIL: 105 шт\n\n"
            "✅ <b>Достатній запас:</b> 15 SKU"
        )
    elif report_type == "critical":
        return (
            "🔴 <b>Критичні позиції</b>\n"
            "🗓️ 26.08.2025 20:00\n\n"
            "⚠️ <b>Менше мінімуму:</b>\n"
            "• BLK-HEART-25-SIL: 45/100 шт\n"
            "• BLK-RING-30-GLD: 30/100 шт\n\n"
            "🚨 <b>Рекомендації:</b>\n"
            "• Замовити BLK-HEART-25-SIL: 255 шт\n"
            "• Замовити BLK-RING-30-GLD: 270 шт"
        )
    else:  # full
        return (
            "📄 <b>Повний звіт по складу</b>\n"
            "🗓️ 26.08.2025 20:00\n\n"
            "📊 <b>Загальна статистика:</b>\n"
            "• Всього SKU: 20\n"
            "• Активних: 20\n"
            "• Критичних: 2\n"
            "• Достатній запас: 15\n\n"
            "🦴 <b>Кістка:</b>\n"
            "• BLK-BONE-25-GLD: 250 шт ✅\n"
            "• BLK-BONE-25-SIL: 180 шт ✅\n"
            "• BLK-BONE-30-GLD: 108 шт 🟡\n"
            "• BLK-BONE-30-SIL: 220 шт ✅\n\n"
            "🟢 <b>Бублик:</b>\n"
            "• BLK-RING-25-GLD: 150 шт ✅\n"
            "• BLK-RING-25-SIL: 200 шт ✅\n"
            "• BLK-RING-30-GLD: 30 шт 🔴\n"
            "• BLK-RING-30-SIL: 180 шт ✅\n\n"
            "<i>...и остальные позиции</i>"
        )