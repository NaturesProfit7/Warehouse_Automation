"""Обработчики команд мониторинга системы."""

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime

from ...services.monitoring_service import get_monitoring_service, ComponentStatus
from ...services.scheduler_service import get_scheduler_service
from ...services.notification_service import get_notification_service
from ...utils.auth import admin_required
from ...utils.logger import get_logger

logger = get_logger(__name__)

router = Router()


@router.message(Command("health"))
@admin_required
async def cmd_health(message: Message):
    """Команда проверки состояния системы."""
    try:
        await message.reply("🔍 Проверяю состояние системы...")
        
        monitoring_service = get_monitoring_service()
        health = await monitoring_service.perform_health_check()
        
        # Формируем сообщение о состоянии
        status_emoji = {
            ComponentStatus.HEALTHY: "✅",
            ComponentStatus.WARNING: "⚠️",
            ComponentStatus.CRITICAL: "❌",
            ComponentStatus.UNKNOWN: "❓"
        }
        
        status_text = {
            ComponentStatus.HEALTHY: "Здоров",
            ComponentStatus.WARNING: "Предупреждение", 
            ComponentStatus.CRITICAL: "Критично",
            ComponentStatus.UNKNOWN: "Неизвестно"
        }
        
        message_text = f"""🏥 <b>Состояние системы</b>
{status_emoji[health.overall_status]} <b>Общий статус:</b> {status_text[health.overall_status]}

⏱️ <b>Время работы:</b> {health.uptime_seconds // 3600}ч {(health.uptime_seconds % 3600) // 60}м
🚨 <b>Критичные проблемы:</b> {health.alerts_count}
⚠️ <b>Предупреждения:</b> {health.warnings_count}

📊 <b>Компоненты:</b>"""
        
        for comp_name, comp_health in health.components.items():
            comp_emoji = status_emoji[comp_health.status]
            comp_status = status_text[comp_health.status]
            
            response_time = ""
            if comp_health.response_time_ms:
                response_time = f" ({comp_health.response_time_ms}мс)"
            
            error_info = ""
            if comp_health.error_message:
                error_info = f"\n  └ {comp_health.error_message}"
            
            message_text += f"\n{comp_emoji} {comp_name.replace('_', ' ').title()}: {comp_status}{response_time}{error_info}"
        
        message_text += f"\n\n🕒 Проверено: {health.check_timestamp.strftime('%H:%M:%S')}"
        
        # Добавляем кнопки для детальной информации
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📈 Тренды", callback_data="health_trends"),
                InlineKeyboardButton(text="🔄 Обновить", callback_data="health_refresh")
            ],
            [
                InlineKeyboardButton(text="⚙️ Планировщик", callback_data="scheduler_status"),
                InlineKeyboardButton(text="🔔 Уведомления", callback_data="notifications_status")
            ]
        ])
        
        await message.reply(message_text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error("Failed to get system health", error=str(e))
        await message.reply(f"❌ Ошибка при проверке состояния системы: {str(e)}")


@router.callback_query(F.data == "health_refresh")
@admin_required
async def callback_health_refresh(callback: CallbackQuery):
    """Обновление информации о состоянии системы."""
    try:
        await callback.message.edit_text("🔍 Обновляю информацию...")
        
        monitoring_service = get_monitoring_service()
        health = await monitoring_service.perform_health_check()
        
        # Повторно формируем сообщение (как в cmd_health)
        status_emoji = {
            ComponentStatus.HEALTHY: "✅",
            ComponentStatus.WARNING: "⚠️", 
            ComponentStatus.CRITICAL: "❌",
            ComponentStatus.UNKNOWN: "❓"
        }
        
        status_text = {
            ComponentStatus.HEALTHY: "Здоров",
            ComponentStatus.WARNING: "Предупреждение",
            ComponentStatus.CRITICAL: "Критично", 
            ComponentStatus.UNKNOWN: "Неизвестно"
        }
        
        message_text = f"""🏥 <b>Состояние системы</b>
{status_emoji[health.overall_status]} <b>Общий статус:</b> {status_text[health.overall_status]}

⏱️ <b>Время работы:</b> {health.uptime_seconds // 3600}ч {(health.uptime_seconds % 3600) // 60}м
🚨 <b>Критичные проблемы:</b> {health.alerts_count}
⚠️ <b>Предупреждения:</b> {health.warnings_count}

📊 <b>Компоненты:</b>"""
        
        for comp_name, comp_health in health.components.items():
            comp_emoji = status_emoji[comp_health.status]
            comp_status = status_text[comp_health.status]
            
            response_time = ""
            if comp_health.response_time_ms:
                response_time = f" ({comp_health.response_time_ms}мс)"
            
            error_info = ""
            if comp_health.error_message:
                error_info = f"\n  └ {comp_health.error_message}"
            
            message_text += f"\n{comp_emoji} {comp_name.replace('_', ' ').title()}: {comp_status}{response_time}{error_info}"
        
        message_text += f"\n\n🕒 Обновлено: {health.check_timestamp.strftime('%H:%M:%S')}"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📈 Тренды", callback_data="health_trends"),
                InlineKeyboardButton(text="🔄 Обновить", callback_data="health_refresh")
            ],
            [
                InlineKeyboardButton(text="⚙️ Планировщик", callback_data="scheduler_status"),
                InlineKeyboardButton(text="🔔 Уведомления", callback_data="notifications_status")
            ]
        ])
        
        await callback.message.edit_text(message_text, reply_markup=keyboard)
        await callback.answer("✅ Информация обновлена")
        
    except Exception as e:
        logger.error("Failed to refresh health status", error=str(e))
        await callback.answer("❌ Ошибка при обновлении")


@router.callback_query(F.data == "scheduler_status")
@admin_required
async def callback_scheduler_status(callback: CallbackQuery):
    """Показ статуса планировщика."""
    try:
        scheduler_service = get_scheduler_service()
        status = scheduler_service.get_job_status()
        
        if status["status"] == "stopped":
            message_text = "⏸️ <b>Планировщик остановлен</b>"
        else:
            message_text = f"""⚙️ <b>Статус планировщика</b>
🟢 <b>Статус:</b> Работает
🌍 <b>Часовой пояс:</b> {status['timezone']}
📋 <b>Задач:</b> {len(status['jobs'])}

<b>Активные задачи:</b>"""
            
            for job in status['jobs']:
                next_run = "—"
                if job['next_run']:
                    try:
                        next_run_dt = datetime.fromisoformat(job['next_run'].replace('Z', '+00:00'))
                        next_run = next_run_dt.strftime('%H:%M:%S')
                    except:
                        next_run = job['next_run'][:19]
                
                message_text += f"\n• <b>{job['name']}</b>\n  ⏰ Следующий запуск: {next_run}"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="health_refresh")]
        ])
        
        await callback.message.edit_text(message_text, reply_markup=keyboard)
        await callback.answer()
        
    except Exception as e:
        logger.error("Failed to get scheduler status", error=str(e))
        await callback.answer("❌ Ошибка получения статуса планировщика")


@router.callback_query(F.data == "notifications_status")
@admin_required
async def callback_notifications_status(callback: CallbackQuery):
    """Показ статуса службы уведомлений."""
    try:
        notification_service = get_notification_service()
        config = notification_service.config
        
        message_text = f"""🔔 <b>Служба уведомлений</b>

⚙️ <b>Конфигурация:</b>
• Критичные: каждые {config.critical_threshold_hours}ч
• Важные: каждые {config.high_threshold_hours}ч 
• Дневная сводка: {'включена' if config.daily_summary_enabled else 'отключена'}
• Час сводки: {config.daily_summary_hour}:00
• Минимум критичных для уведомления: {config.min_critical_items}
• Максимум позиций в сообщении: {config.max_items_per_message}

📨 <b>Последние уведомления:</b>"""
        
        # Показываем кэш последних уведомлений если есть
        if hasattr(notification_service, '_last_alerts') and notification_service._last_alerts:
            for alert_type, last_time in notification_service._last_alerts.items():
                time_str = last_time.strftime('%d.%m.%Y %H:%M')
                message_text += f"\n• {alert_type}: {time_str}"
        else:
            message_text += "\n• Пока нет отправленных уведомлений"
        
        # Кнопки управления
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🧪 Тест критичных", callback_data="test_critical_alert"),
                InlineKeyboardButton(text="📊 Сводка сейчас", callback_data="force_daily_summary")
            ],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="health_refresh")]
        ])
        
        await callback.message.edit_text(message_text, reply_markup=keyboard)
        await callback.answer()
        
    except Exception as e:
        logger.error("Failed to get notifications status", error=str(e))
        await callback.answer("❌ Ошибка получения статуса уведомлений")


@router.callback_query(F.data == "test_critical_alert")
@admin_required
async def callback_test_critical_alert(callback: CallbackQuery):
    """Тестовая проверка критичных остатков."""
    try:
        await callback.answer("🔍 Перевіряю критичні залишки...")
        
        notification_service = get_notification_service()
        alert = await notification_service.check_critical_stock()
        
        if alert:
            await notification_service.send_telegram_alert(alert)
            await callback.message.reply("✅ Тест выполнен. Уведомление отправлено.")
        else:
            await callback.message.reply("ℹ️ Критичних залишків не виявлено.")
            
    except Exception as e:
        logger.error("Failed to test critical alert", error=str(e))
        await callback.answer("❌ Ошибка при тестировании")


@router.callback_query(F.data == "force_daily_summary")
@admin_required
async def callback_force_daily_summary(callback: CallbackQuery):
    """Принудительная генерация ежедневной сводки."""
    try:
        await callback.answer("📊 Генерирую ежедневную сводку...")
        
        notification_service = get_notification_service()
        summary = await notification_service.generate_daily_summary()
        
        if summary:
            await callback.message.reply(summary)
        else:
            await callback.message.reply("❌ Не удалось сгенерировать сводку")
            
    except Exception as e:
        logger.error("Failed to generate daily summary", error=str(e))
        await callback.answer("❌ Ошибка при генерации сводки")


@router.callback_query(F.data == "health_trends")
@admin_required
async def callback_health_trends(callback: CallbackQuery):
    """Показ трендов состояния системы."""
    try:
        monitoring_service = get_monitoring_service()
        summary = monitoring_service.get_system_summary()
        
        if "error" in summary:
            await callback.answer("❌ Нет данных о трендах")
            return
        
        message_text = f"""📈 <b>Сводка системы</b>

🏥 <b>Текущее состояние:</b> {summary['overall_status']}
⏱️ <b>Время работы:</b> {summary['uptime_hours']}ч
✅ <b>Здоровых компонентов:</b> {summary['healthy_components']}/{summary['total_components']}
🚨 <b>Критичных проблем:</b> {summary['alerts_count']}
⚠️ <b>Предупреждений:</b> {summary['warnings_count']}

📊 <b>Компоненты:</b>"""
        
        for comp_name, comp_info in summary['component_summary'].items():
            status_emoji = "✅" if comp_info['status'] == 'healthy' else "⚠️" if comp_info['status'] == 'warning' else "❌"
            response_time = f" ({comp_info['response_time_ms']}мс)" if comp_info['response_time_ms'] else ""
            
            message_text += f"\n{status_emoji} {comp_name.replace('_', ' ').title()}{response_time}"
        
        message_text += f"\n\n🕒 Последняя проверка: {summary['last_check'][:19]}"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="health_refresh")]
        ])
        
        await callback.message.edit_text(message_text, reply_markup=keyboard)
        await callback.answer()
        
    except Exception as e:
        logger.error("Failed to get health trends", error=str(e))
        await callback.answer("❌ Ошибка получения трендов")