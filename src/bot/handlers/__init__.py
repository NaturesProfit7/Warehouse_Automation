"""Обработчики команд и сообщений Telegram бота."""

import asyncio
from typing import Any

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ...core.exceptions import StockCalculationError, IntegrationError, MappingError
from ...core.models import MovementSourceType
from ...services.stock_service import get_stock_service
from ...services.report_service import get_report_service
from ...utils.logger import get_logger
from ..keyboards import (
    get_analytics_menu_keyboard,
    get_analytics_period_keyboard,
    get_blank_type_keyboard,
    get_bone_size_keyboard,
    get_cancel_keyboard,
    get_color_keyboard,
    get_confirmation_keyboard,
    get_correction_type_keyboard,
    get_main_menu_keyboard,
    get_report_type_keyboard,
    get_ring_size_keyboard,
    get_round_size_keyboard,
    get_shaped_form_keyboard,
)
from ..states import ReceiptStates, CorrectionStates

logger = get_logger(__name__)

# Создаем роутер для обработчиков
router = Router()

# Подключаем роутер мониторинга
from .monitoring import router as monitoring_router
router.include_router(monitoring_router)


# === ОСНОВНЫЕ КОМАНДЫ ===

@router.message(Command("start"))
async def cmd_start(message: Message, user_info: dict[str, Any]) -> None:
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
        "• /correction [SKU] [КІЛЬКІСТЬ] — швидка корекція\n\n"
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

    # Формируем SKU для отображения
    data = await state.get_data()
    sku = _build_sku_from_data(data)
    await state.update_data(sku=sku)

    color_names = {"GLD": "🟡 Золото", "SIL": "⚪ Срібло"}
    color_name = color_names.get(color, color)

    # Проверяем, это коррекция или приход
    if "correction_type" in data:
        # Это коррекция - переходим в состояние коррекции
        await state.set_state(CorrectionStates.waiting_for_quantity)
        correction_type = data["correction_type"]
        
        if correction_type == "add":
            instruction = "Введіть кількість для <b>додавання</b>:"
        elif correction_type == "subtract":
            instruction = "Введіть кількість для <b>вирахування</b>:"
        elif correction_type == "set":
            instruction = "Введіть <b>точний залишок</b>:"
        else:
            instruction = "Введіть кількість:"
            
        text = (
            f"{color_name}\n\n"
            f"🏷️ <b>SKU:</b> <code>{sku}</code>\n\n"
            f"{instruction}"
        )
    else:
        # Это обычный приход
        await state.set_state(ReceiptStates.waiting_for_quantity)
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

    reports = {
        "short": "📋 <b>Короткий звіт</b>\n\n🔄 Завантаження...",
        "full": "📄 <b>Повний звіт</b>\n\n🔄 Завантаження...",
        "critical": "🔴 <b>Критичні позиції</b>\n\n🔄 Завантаження..."
    }

    text = reports.get(report_type, "❌ Невідомий тип звіту")

    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()

    try:
        # Получаем сервис отчетов
        report_service = get_report_service()
        
        if report_type == "short":
            report_text = await report_service.generate_summary_report()
        elif report_type == "critical":
            report_text = await report_service.generate_critical_stock_report()
        elif report_type == "full":
            report_text = await report_service.generate_full_stock_report()
        else:
            report_text = "❌ Невідомий тип звіту"
        
        # Ограничиваем длину сообщения (Telegram лимит 4096 символов)
        if len(report_text) > 4000:
            report_text = report_text[:4000] + "\n\n<i>...звіт обрізано</i>"
            
    except Exception as e:
        logger.error("Failed to generate report", error=str(e), report_type=report_type)
        report_text = (
            f"❌ <b>Помилка генерації звіту</b>\n\n"
            f"Спробуйте ще раз або зверніться до адміністратора.\n"
            f"Помилка: {str(e)}"
        )

    await callback.message.edit_text(
        report_text,
        reply_markup=get_main_menu_keyboard(),
        parse_mode="HTML"
    )


# === КОРРЕКТИРОВКИ (ТОЛЬКО ДЛЯ АДМИНИСТРАТОРОВ) ===

@router.message(Command("correction"))
async def cmd_correction(message: Message, is_admin: bool, state: FSMContext) -> None:
    """Команда корректировки остатков."""
    
    if not is_admin:
        await message.answer("❌ Недостатньо прав доступу")
        return
    
    await state.set_state(CorrectionStates.waiting_for_sku)
    text = "⚙️ <b>Корекція залишків</b>\n\nОберіть тип операції:"
    
    await message.answer(
        text,
        reply_markup=get_correction_type_keyboard(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "correction")
async def start_correction(callback: CallbackQuery, is_admin: bool, state: FSMContext) -> None:
    """Начало процесса корректировки."""

    if not is_admin:
        await callback.answer("❌ Недостатньо прав доступу", show_alert=True)
        return

    await state.set_state(CorrectionStates.waiting_for_sku)
    text = "⚙️ <b>Корекція залишків</b>\n\nОберіть тип операції:"

    await callback.message.edit_text(
        text,
        reply_markup=get_correction_type_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(CorrectionStates.waiting_for_sku, F.data.startswith("correction_"))
async def process_correction_type(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработка выбора типа коррекции."""
    
    correction_type = callback.data.replace("correction_", "")
    await state.update_data(correction_type=correction_type)
    
    # Переходим к выбору типа заготовки
    await state.set_state(ReceiptStates.waiting_for_type)
    
    if correction_type == "add":
        text = "➕ <b>Додавання до залишків</b>\n\nОберіть тип заготовки:"
    elif correction_type == "subtract":
        text = "➖ <b>Вирахування із залишків</b>\n\nОберіть тип заготовки:"
    elif correction_type == "set":
        text = "🔄 <b>Встановлення точного залишку</b>\n\nОберіть тип заготовки:"
    else:
        await callback.answer("❌ Невідомий тип корекції")
        return
    
    await callback.message.edit_text(
        text,
        reply_markup=get_blank_type_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


# Используем существующие обработчики выбора типа, размера и цвета из прихода
# Но переопределим обработчик для количества в контексте коррекции

@router.message(CorrectionStates.waiting_for_quantity)
async def process_correction_quantity_input(message: Message, state: FSMContext) -> None:
    """Обработка ввода количества для коррекции."""
    
    try:
        data = await state.get_data()
        correction_type = data["correction_type"]
        sku = data["sku"]
        
        # Парсим количество
        qty_str = message.text.strip()
        
        if correction_type == "set":
            # Для типа "set" - абсолютное значение
            if not qty_str.isdigit():
                await message.answer("❌ Для встановлення точного залишку введіть позитивне число")
                return
            target_qty = int(qty_str)
            if target_qty < 0:
                await message.answer("❌ Кількість не може бути від'ємною")
                return
                
            await state.update_data(target_qty=target_qty, adjustment=None)
            display_change = f"встановити {target_qty}"
        else:
            # Для add/subtract - относительное изменение
            try:
                adjustment = int(qty_str)
                if correction_type == "add":
                    if adjustment <= 0:
                        await message.answer("❌ Для додавання введіть позитивне число")
                        return
                    display_change = f"+{adjustment}"
                elif correction_type == "subtract":
                    if adjustment >= 0:
                        adjustment = -adjustment  # Автоматически делаем отрицательным
                    display_change = f"{adjustment}"
                else:
                    await message.answer("❌ Невідомий тип корекції")
                    return
            except ValueError:
                await message.answer("❌ Введіть правильне число")
                return
                
            await state.update_data(adjustment=adjustment, target_qty=None)
        
        await state.update_data(quantity_display=display_change)
        await state.set_state(CorrectionStates.waiting_for_reason)
        
        await message.answer(
            f"⚙️ <b>Підтвердження корекції</b>\n\n"
            f"SKU: <code>{sku}</code>\n"
            f"Зміна: <code>{display_change}</code>\n\n"
            f"Введіть причину корекції:",
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error("Error processing correction quantity", error=str(e))
        await message.answer("❌ Помилка обробки. Спробуйте ще раз.")


@router.message(CorrectionStates.waiting_for_reason)
async def process_correction_reason(message: Message, state: FSMContext) -> None:
    """Обработка ввода причины коррекции."""
    
    reason = message.text.strip()
    if len(reason) < 5:
        await message.answer("❌ Причина має містити не менше 5 символів")
        return
        
    await state.update_data(reason=reason)
    
    # Получаем все данные
    data = await state.get_data()
    sku = data["sku"]
    quantity_display = data["quantity_display"]
    correction_type = data["correction_type"]
    
    # Выполняем коррекцию
    try:
        stock_service = get_stock_service()
        
        if correction_type == "set":
            # Для set - вычисляем adjustment
            current_stock = stock_service.get_current_stock(sku)
            target_qty = data["target_qty"]
            adjustment = target_qty - current_stock.on_hand
        else:
            adjustment = data["adjustment"]
            
        if adjustment == 0:
            await message.answer("❌ Корекція не потрібна - залишок не змінився")
            await state.clear()
            return
            
        # Выполняем коррекцию
        movement = await stock_service.add_correction_movement(
            blank_sku=sku,
            quantity_adjustment=adjustment,
            user=f"{message.from_user.full_name} ({message.from_user.id})",
            reason=reason
        )
        
        await message.answer(
            f"✅ <b>Корекція виконана!</b>\n\n"
            f"SKU: <code>{sku}</code>\n"
            f"Зміна: <code>{quantity_display}</code>\n"
            f"Новий залишок: <b>{movement.balance_after}</b>\n"
            f"ID руху: <code>{movement.id}</code>\n"
            f"Причина: {reason}",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="HTML"
        )
        
        logger.info(
            "Correction completed successfully",
            sku=sku,
            adjustment=adjustment,
            new_balance=movement.balance_after,
            user_id=message.from_user.id,
            reason=reason
        )
        
    except Exception as e:
        logger.error("Failed to execute correction", sku=sku, error=str(e))
        await message.answer(
            f"❌ Помилка виконання корекції: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        
    await state.clear()


# === АНАЛИТИКА ===

@router.callback_query(F.data == "analytics")
async def show_analytics_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Показ меню аналитики."""
    
    await state.clear()  # Очищаем состояние
    
    text = "📈 <b>Аналитика заготовок</b>\n\nВыберите тип анализа:"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_analytics_menu_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.in_(["top_sales", "turnover_analysis", "purchase_recommendations"]))
async def select_analytics_period(callback: CallbackQuery, state: FSMContext) -> None:
    """Выбор периода для аналитики."""
    
    analytics_type = callback.data
    await state.update_data(analytics_type=analytics_type)
    
    type_names = {
        "top_sales": "📈 Топ продаж",
        "turnover_analysis": "⚡ Оборачиваемость",
        "purchase_recommendations": "🎯 Рекомендации закупок"
    }
    
    text = f"{type_names[analytics_type]}\n\nВыберите период для анализа:"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_analytics_period_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("period_"))
async def process_analytics_period(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработка выбора периода и генерация отчета."""
    
    period_str = callback.data.replace("period_", "")
    days = int(period_str)
    
    data = await state.get_data()
    analytics_type = data.get("analytics_type")
    
    if not analytics_type:
        await callback.answer("❌ Ошибка: тип аналитики не выбран")
        return
    
    # Показываем индикатор загрузки
    await callback.message.edit_text(
        "⏳ <b>Генерируем отчет...</b>\n\nЭто может занять несколько секунд",
        parse_mode="HTML"
    )
    
    try:
        report_service = get_report_service()
        
        if analytics_type == "top_sales":
            report_data = await report_service.generate_top_sales_report(days)
            text = format_top_sales_report(report_data)
        elif analytics_type == "turnover_analysis":
            report_data = await report_service.generate_turnover_analysis(days)
            text = format_turnover_report(report_data)
        elif analytics_type == "purchase_recommendations":
            report_data = await report_service.generate_purchase_recommendations(days)
            text = format_purchase_recommendations_report(report_data)
        else:
            text = "❌ Неизвестный тип аналитики"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_analytics_menu_keyboard(),
            parse_mode="HTML"
        )
        
        logger.info(
            "Analytics report generated",
            type=analytics_type,
            days=days,
            user_id=callback.from_user.id
        )
        
    except Exception as e:
        logger.error("Failed to generate analytics report", error=str(e), type=analytics_type)
        await callback.message.edit_text(
            f"❌ <b>Ошибка генерации отчета</b>\n\n{str(e)}",
            reply_markup=get_analytics_menu_keyboard(),
            parse_mode="HTML"
        )
    
    await callback.answer()


def format_top_sales_report(data: dict) -> str:
    """Форматирование отчета топ продаж."""
    
    period = data["period_days"]
    top_skus = data["top_skus"]
    total_outbound = data["total_outbound"]
    total_orders = data["total_orders"]
    
    text = f"📈 <b>ТОП ПРОДАЖ за {period} дней</b>\n\n"
    
    if not top_skus:
        text += "📭 Нет данных о расходах за выбранный период"
        return text
    
    text += f"📊 Общая статистика:\n"
    text += f"• Всего расходов: {total_outbound} шт\n"
    text += f"• Количество заказов: {total_orders}\n\n"
    
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    for i, (sku, stats) in enumerate(top_skus):
        medal = medals[i] if i < len(medals) else f"{i+1}."
        total_qty = stats["total_quantity"]
        order_count = stats["order_count"]
        
        text += f"{medal} <code>{sku}</code>\n"
        text += f"   Расход: <b>{total_qty} шт</b> | Заказов: {order_count}\n\n"
    
    return text


def format_turnover_report(data: dict) -> str:
    """Форматирование отчета оборачиваемости."""
    
    period = data["period_days"]
    fast_movers = data["fast_movers"]
    medium_movers = data["medium_movers"]
    slow_movers = data["slow_movers"]
    
    text = f"⚡ <b>ОБОРАЧИВАЕМОСТЬ за {period} дней</b>\n\n"
    
    def format_items(items, limit=5):
        result = ""
        for i, item in enumerate(items[:limit]):
            sku = item["sku"]
            weekly = item["weekly_consumption"]
            stock = item["current_stock"]
            days_left = item["days_to_stockout"]
            
            days_text = f"({days_left}д до конца)" if days_left else "(не закончится)"
            result += f"• <code>{sku}</code>: {weekly:.1f} шт/нед | {stock} шт {days_text}\n"
        return result
    
    if fast_movers:
        text += f"🔥 <b>БЫСТРООБОРОТНЫЕ</b> (≥10 шт/неделю):\n"
        text += format_items(fast_movers)
        text += "\n"
    
    if medium_movers:
        text += f"🟡 <b>СРЕДНИЕ</b> (5-10 шт/неделю):\n"
        text += format_items(medium_movers)
        text += "\n"
    
    if slow_movers:
        text += f"🐌 <b>МЕДЛЕННЫЕ</b> (&lt;5 шт/неделю):\n"
        # Показываем только первые 3 медленных
        text += format_items(slow_movers, limit=3)
        if len(slow_movers) > 3:
            text += f"... и еще {len(slow_movers) - 3} товаров\n"
    
    return text


def format_purchase_recommendations_report(data: dict) -> str:
    """Форматирование рекомендаций по закупкам."""
    
    period = data["period_days"]
    critical = data["critical"]
    high_priority = data["high_priority"]
    medium_priority = data["medium_priority"]
    total_cost = data["total_estimated_cost"]
    
    text = f"🎯 <b>РЕКОМЕНДАЦИИ ЗАКУПОК</b>\n"
    text += f"(Анализ за {period} дней)\n\n"
    
    def format_recommendations(items, limit=5):
        result = ""
        for item in items[:limit]:
            sku = item["sku"]
            current = item["current_stock"]
            recommended = item["recommended_qty"]
            reason = item["reason"].replace("<", "&lt;").replace(">", "&gt;")  # Экранируем HTML
            
            result += f"• <code>{sku}</code>\n"
            result += f"  Есть: {current} → Заказать: <b>{recommended} шт</b>\n"
            result += f"  Причина: {reason}\n\n"
        return result
    
    if critical:
        text += f"🚨 <b>КРИТИЧНО</b> ({len(critical)}):\n"
        text += format_recommendations(critical, 3)
    
    if high_priority:
        text += f"🟠 <b>ВЫСОКИЙ ПРИОРИТЕТ</b> ({len(high_priority)}):\n"
        text += format_recommendations(high_priority, 3)
    
    if medium_priority:
        text += f"🟡 <b>СРЕДНИЙ ПРИОРИТЕТ</b> ({len(medium_priority)}):\n"
        text += format_recommendations(medium_priority, 2)
    
    if not (critical or high_priority or medium_priority):
        text += "✅ <b>Все заготовки в достатке!</b>\n"
        text += "Дополнительные закупки не требуются.\n\n"
    
    return text


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

def _build_sku_from_data(data: dict[str, Any]) -> str:
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

    try:
        data = await state.get_data()
        sku = _build_sku_from_data(data)
        quantity = data.get("quantity", 0)
        user_id = message.from_user.id if message else None
        user_name = message.from_user.full_name if message else "Unknown"

        # Получаем сервис управления остатками
        stock_service = get_stock_service()
        
        # Создаем приходное движение
        movement = await stock_service.add_receipt_movement(
            blank_sku=sku,
            quantity=quantity,
            user=f"{user_name} ({user_id})" if user_id else user_name,
            note=f"Приход через Telegram бот от {user_name}",
            source_type=MovementSourceType.TELEGRAM
        )
        
        logger.info(
            "Receipt added successfully",
            sku=sku,
            quantity=quantity,
            balance_after=movement.balance_after,
            user_id=user_id,
            movement_id=str(movement.id)
        )

        text = (
            f"✅ <b>Приход успішно додано!</b>\n\n"
            f"🏷️ <b>SKU:</b> <code>{sku}</code>\n"
            f"📦 <b>Кількість:</b> +{quantity} шт\n"
            f"📊 <b>Залишок:</b> {movement.balance_after} шт\n\n"
            f"Операцію збережено в систему."
        )

    except (StockCalculationError, MappingError, IntegrationError) as e:
        logger.error(
            "Failed to save receipt", 
            error=str(e),
            sku=sku,
            quantity=quantity,
            user_id=user_id
        )
        text = (
            f"❌ <b>Помилка збереження!</b>\n\n"
            f"🏷️ <b>SKU:</b> <code>{sku}</code>\n"
            f"📦 <b>Кількість:</b> +{quantity} шт\n\n"
            f"Помилка: {str(e)}\n\n"
            f"Спробуйте ще раз або зверніться до адміністратора."
        )
    
    except Exception as e:
        logger.error(
            "Unexpected error saving receipt",
            error=str(e),
            user_id=user_id
        )
        text = (
            f"❌ <b>Непередбачена помилка!</b>\n\n"
            f"Спробуйте ще раз або зверніться до адміністратора."
        )

    keyboard = get_main_menu_keyboard()

    if is_callback:
        await message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    await state.clear()


# === ОСТАТКИ ===

@router.callback_query(F.data == "stock")
async def show_stock_info(callback: CallbackQuery) -> None:
    """Показ информации об остатках."""
    
    await callback.message.edit_text(
        "📦 <b>Інформація про залишки</b>\n\n🔄 Завантаження...",
        parse_mode="HTML"
    )
    await callback.answer()
    
    try:
        stock_service = get_stock_service()
        current_stock = await stock_service.get_all_current_stock()
        
        # Группируем по типам для удобного отображения
        grouped_stock = {}
        for stock in current_stock:
            sku_parts = stock.blank_sku.split('-')
            if len(sku_parts) >= 2:
                sku_type = sku_parts[1]
                if sku_type not in grouped_stock:
                    grouped_stock[sku_type] = []
                grouped_stock[sku_type].append(stock)
        
        # Формируем отчет
        report_lines = ["📦 <b>Поточні залишки</b>\n"]
        
        # Статистика
        total_items = sum(stock.on_hand for stock in current_stock)
        low_stock_count = sum(1 for stock in current_stock if stock.on_hand <= 50)
        
        report_lines.append(
            f"📊 <b>Статистика:</b>\n"
            f"• Всього позицій: {len(current_stock)}\n"
            f"• Загальна кількість: {total_items} шт\n"
            f"• Низький рівень: {low_stock_count} позицій\n\n"
        )
        
        # Типы заготовок
        type_names = {
            "BONE": "🦴 Кістка",
            "RING": "🟢 Бублик", 
            "ROUND": "⚪ Круглий",
            "HEART": "❤️ Серце",
            "FLOWER": "🌸 Квітка",
            "CLOUD": "☁️ Хмарка"
        }
        
        for sku_type in ["BONE", "RING", "ROUND", "HEART", "FLOWER", "CLOUD"]:
            if sku_type in grouped_stock:
                type_name = type_names.get(sku_type, sku_type)
                report_lines.append(f"<b>{type_name}:</b>\n")
                
                for stock in sorted(grouped_stock[sku_type], key=lambda x: x.blank_sku):
                    # Определяем статус остатка
                    if stock.on_hand <= 50:
                        status = "🔴"
                    elif stock.on_hand <= 100:
                        status = "🟡"
                    else:
                        status = "✅"
                    
                    # Форматируем SKU для отображения
                    sku_display = stock.blank_sku.replace("BLK-", "").replace("-", " ")
                    report_lines.append(f"• {sku_display}: {stock.on_hand} шт {status}\n")
                
                report_lines.append("\n")
        
        report_text = "".join(report_lines)
        
        # Ограничиваем длину
        if len(report_text) > 4000:
            report_text = report_text[:4000] + "\n\n<i>...звіт обрізано</i>"
            
    except Exception as e:
        logger.error("Failed to load stock info", error=str(e))
        report_text = (
            "❌ <b>Помилка завантаження даних</b>\n\n"
            "Спробуйте ще раз або зверніться до адміністратора."
        )
    
    await callback.message.edit_text(
        report_text,
        reply_markup=get_main_menu_keyboard(),
        parse_mode="HTML"
    )
