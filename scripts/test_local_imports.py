#!/usr/bin/env python3
"""Тест локального импорта и проверки основных компонентов."""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_imports():
    """Тестирование основных импортов."""
    print("🔍 Тестирую импорты компонентов...")
    
    # Тест основных модулей
    try:
        from src.core.models import Movement, CurrentStock, ReplenishmentRecommendation
        print("✅ Core models imported successfully")
    except Exception as e:
        print(f"❌ Core models import failed: {e}")
        return False
        
    try:
        from src.scheduler.jobs import ScheduledJobs
        print("✅ Scheduler jobs imported successfully")
    except Exception as e:
        print(f"❌ Scheduler jobs import failed: {e}")
        return False
        
    try:
        from src.scheduler.runner import SchedulerRunner
        print("✅ Scheduler runner imported successfully")
    except Exception as e:
        print(f"❌ Scheduler runner import failed: {e}")
        return False
        
    try:
        from src.bot.keyboards import get_main_menu_keyboard, get_blank_type_keyboard
        print("✅ Bot keyboards imported successfully")
    except Exception as e:
        print(f"❌ Bot keyboards import failed: {e}")
        return False
        
    try:
        from src.bot.handlers import router
        print("✅ Bot handlers imported successfully")
    except Exception as e:
        print(f"❌ Bot handlers import failed: {e}")
        return False
        
    return True

def test_scheduler_job_creation():
    """Тест создания задач планировщика."""
    print("\n📅 Тестирую создание задач планировщика...")
    
    try:
        from src.scheduler.jobs import ScheduledJobs
        
        # Создаем экземпляр (без реальных API)
        class MockClient:
            def get_master_blanks(self):
                return []
            def get_current_stock(self):
                return []
                
        class MockService:
            async def get_all_current_stock(self):
                return []
                
        # Создаем моки
        jobs = ScheduledJobs()
        jobs.sheets_client = MockClient()
        jobs.stock_service = MockService()
        
        print("✅ ScheduledJobs created successfully with mocks")
        
        # Проверяем методы
        assert hasattr(jobs, 'check_stock_levels'), "check_stock_levels method exists"
        assert hasattr(jobs, 'daily_stock_calculation'), "daily_stock_calculation method exists"
        assert hasattr(jobs, '_send_combined_stock_alert'), "_send_combined_stock_alert method exists"
        
        print("✅ All required methods exist")
        return True
        
    except Exception as e:
        print(f"❌ Scheduler job creation failed: {e}")
        return False

def test_keyboard_localization():
    """Тест локализации клавиатур."""
    print("\n🌐 Тестирую локализацию клавиатур...")
    
    try:
        from src.bot.keyboards import get_main_menu_keyboard
        
        keyboard = get_main_menu_keyboard()
        
        # Проверяем украинский текст в кнопках
        buttons_text = []
        for row in keyboard.inline_keyboard:
            for button in row:
                buttons_text.append(button.text)
                
        expected_texts = ["Поставка", "Залишки", "Звіт", "Коригування", "Аналітика"]
        
        for expected in expected_texts:
            found = any(expected in text for text in buttons_text)
            if found:
                print(f"✅ Found localized text: {expected}")
            else:
                print(f"❌ Missing localized text: {expected}")
                return False
                
        print("✅ All keyboard localization successful")
        return True
        
    except Exception as e:
        print(f"❌ Keyboard localization test failed: {e}")
        return False

def test_sheets_cleanup_methods():
    """Тест методов очистки Google Sheets."""
    print("\n🧹 Тестирую методы очистки Google Sheets...")
    
    try:
        from src.integrations.sheets import GoogleSheetsClient
        
        # Проверяем что методы добавлены
        assert hasattr(GoogleSheetsClient, 'clear_worksheet_data'), "clear_worksheet_data method exists"
        assert hasattr(GoogleSheetsClient, 'clear_data_sheets'), "clear_data_sheets method exists"
        
        print("✅ Google Sheets cleanup methods added successfully")
        return True
        
    except Exception as e:
        print(f"❌ Sheets cleanup methods test failed: {e}")
        return False

def main():
    """Основной тест."""
    print("🚀 Запуск локальных тестов после обновлений...\n")
    
    tests = [
        ("Импорты", test_imports),
        ("Планировщик", test_scheduler_job_creation), 
        ("Локализация", test_keyboard_localization),
        ("Очистка Sheets", test_sheets_cleanup_methods)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
    
    print(f"\n📊 Результат тестов: {passed}/{total} прошли успешно")
    
    if passed == total:
        print("🎉 Все тесты пройдены! Система готова к деплою.")
        return True
    else:
        print("⚠️ Некоторые тесты не прошли. Требуется исправление.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)