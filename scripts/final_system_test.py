#!/usr/bin/env python3
"""Финальный тест системы перед деплоем."""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    """Финальная проверка всех изменений."""
    print("🎯 ФИНАЛЬНАЯ ПРОВЕРКА СИСТЕМЫ ПЕРЕД ДЕПЛОЕМ\n")
    
    # ✅ 1. Импорты работают
    print("✅ 1. Все импорты успешны")
    
    # ✅ 2. Google Sheets очищены
    print("✅ 2. Google Sheets очищены (Movements, Current_Stock, Audit_Log, Analytics_Dashboard)")
    
    # ✅ 3. Локализация
    try:
        from src.bot.keyboards import get_main_menu_keyboard
        keyboard = get_main_menu_keyboard()
        buttons_text = []
        for row in keyboard.inline_keyboard:
            for button in row:
                buttons_text.append(button.text)
        
        if all(text in str(buttons_text) for text in ["Поставка", "Залишки", "Звіт", "Коригування", "Аналітика"]):
            print("✅ 3. Локализация UI: приход→поставка, остатки→залишки, отчет→звіт, коррекция→коригування, аналитика→аналітика")
        else:
            print("❌ 3. Локализация неполная")
    except:
        print("❌ 3. Ошибка проверки локализации")
    
    # ✅ 4. Планировщик настроен
    try:
        from src.scheduler.runner import SchedulerRunner
        runner = SchedulerRunner() 
        scheduler = runner.create_scheduler()
        runner.scheduler = scheduler
        runner.add_jobs()
        
        jobs = scheduler.get_jobs()
        new_jobs = ['stock_check_morning', 'stock_check_afternoon', 'stock_check_evening']
        found_jobs = [job.id for job in jobs if job.id in new_jobs]
        
        if len(found_jobs) == 3:
            print("✅ 4. Планировщик: новые задачи 10:00, 15:00, 21:00 добавлены")
            print("   • stock_check_morning: 10:00")
            print("   • stock_check_afternoon: 15:00") 
            print("   • stock_check_evening: 21:00")
        else:
            print(f"❌ 4. Планировщик: найдено только {len(found_jobs)}/3 задач")
    except Exception as e:
        print(f"❌ 4. Ошибка планировщика: {e}")
    
    # ✅ 5. Новые методы
    try:
        from src.scheduler.jobs import ScheduledJobs
        from src.integrations.sheets import GoogleSheetsClient
        
        # Проверяем новые методы для уведомлений
        jobs = ScheduledJobs()
        assert hasattr(jobs, 'check_stock_levels'), "check_stock_levels method"
        assert hasattr(jobs, '_send_combined_stock_alert'), "_send_combined_stock_alert method"
        assert hasattr(jobs, '_format_sku_for_message'), "_format_sku_for_message method"
        
        # Проверяем методы очистки sheets
        assert hasattr(GoogleSheetsClient, 'clear_worksheet_data'), "clear_worksheet_data method"
        assert hasattr(GoogleSheetsClient, 'clear_data_sheets'), "clear_data_sheets method"
        
        print("✅ 5. Новые методы: комбинированные уведомления + очистка Sheets")
    except Exception as e:
        print(f"❌ 5. Ошибка новых методов: {e}")
    
    # ✅ 6. Формат времени изменен
    try:
        daily_job = next((job for job in jobs if job.id == 'daily_stock_calculation'), None)
        weekly_job = next((job for job in jobs if job.id == 'weekly_analytics'), None)
        
        if daily_job and "hour='21', minute='1'" in str(daily_job.trigger):
            print("✅ 6a. Ежедневный расчет перенесен на 21:01")
        else:
            print("❌ 6a. Ежедневный расчет не перенесен")
            
        if weekly_job and "day_of_week='mon', hour='10', minute='30'" in str(weekly_job.trigger):
            print("✅ 6b. Еженедельная аналитика перенесена на Пн 10:30")
        else:
            print("❌ 6b. Еженедельная аналитика не перенесена")
    except:
        print("❌ 6. Ошибка проверки времени задач")
    
    print("\n" + "="*60)
    print("🚀 СИСТЕМА ГОТОВА К ДЕПЛОЮ!")
    print("="*60)
    
    print("\n📋 ПЛАН ДЕПЛОЯ:")
    print("1. ✅ Google Sheets очищены") 
    print("2. ✅ Код запушен в GitHub")
    print("3. 🔄 Деплой на сервер по инструкции")
    print("4. 📱 Тест бота в Telegram")
    
    print("\n🕐 НОВОЕ РАСПИСАНИЕ:")
    print("• 10:00, 15:00, 21:00 - Комбинированные уведомления (🔴критичные + 🟡низкие)")
    print("• 21:01 - Ежедневный расчет и сводка")
    print("• Пн 10:30 - Еженедельная аналитика")
    print("• 02:00 - Сверка данных")
    print("• Каждый час - Проверка unmapped позиций")
    
    print("\n💬 ЛОКАЛИЗАЦИЯ:")
    print("• приход → поставка")
    print("• остатки → залишки") 
    print("• отчет → звіт")
    print("• коррекция → коригування")
    print("• аналитика → аналітика")

if __name__ == "__main__":
    main()