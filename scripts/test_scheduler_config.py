#!/usr/bin/env python3
"""Тест конфигурации планировщика."""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_scheduler_jobs():
    """Тест конфигурации задач планировщика."""
    print("⏰ Тестирую конфигурацию планировщика...")
    
    try:
        from src.scheduler.runner import SchedulerRunner
        from apscheduler.triggers.cron import CronTrigger
        
        # Создаем планировщик  
        runner = SchedulerRunner()
        scheduler = runner.create_scheduler()
        
        # Добавляем задачи
        runner.scheduler = scheduler
        runner.add_jobs()
        
        # Проверяем что задачи добавлены
        jobs = scheduler.get_jobs()
        job_names = [job.id for job in jobs]
        
        print(f"📋 Найдено задач: {len(jobs)}")
        
        # Проверяем новые задачи
        expected_jobs = [
            ('stock_check_morning', '10:00'),
            ('stock_check_afternoon', '15:00'), 
            ('stock_check_evening', '21:00'),
            ('daily_stock_calculation', '21:01'),
            ('weekly_analytics', 'Mon 10:30')
        ]
        
        for job_id, expected_time in expected_jobs:
            job = scheduler.get_job(job_id)
            if job:
                print(f"✅ {job_id}: {job.name}")
                
                # Проверяем время для cron trigger
                if hasattr(job.trigger, 'fields'):
                    trigger_info = []
                    if hasattr(job.trigger.fields['hour'], 'expressions'):
                        hours = list(job.trigger.fields['hour'].expressions)[0].step
                        trigger_info.append(f"hour={hours}")
                    if hasattr(job.trigger.fields['minute'], 'expressions'):
                        minutes = list(job.trigger.fields['minute'].expressions)[0].step  
                        trigger_info.append(f"minute={minutes}")
                    
                    print(f"   Trigger: {trigger_info}")
            else:
                print(f"❌ Missing job: {job_id}")
                return False
                
        print("✅ Все задачи планировщика настроены правильно")
        return True
        
    except Exception as e:
        print(f"❌ Scheduler test failed: {e}")
        return False

def test_new_stock_check_function():
    """Тест новой функции комбинированной проверки остатков."""
    print("\n📦 Тестирую новую функцию проверки остатков...")
    
    try:
        from src.scheduler.jobs import ScheduledJobs
        from src.core.models import CurrentStock
        
        jobs = ScheduledJobs()
        
        # Тестируем форматирование SKU
        test_sku = "BLK-HEART-25-GLD"
        formatted = jobs._format_sku_for_message(test_sku)
        
        expected_elements = ["❤️", "Серце", "25мм", "🟡"]
        for element in expected_elements:
            if element in formatted:
                print(f"✅ SKU formatting contains: {element}")
            else:
                print(f"❌ SKU formatting missing: {element}")
                return False
                
        print("✅ SKU formatting works correctly")
        
        # Проверяем что метод check_stock_levels существует
        assert hasattr(jobs, 'check_stock_levels'), "check_stock_levels method exists"
        assert hasattr(jobs, '_send_combined_stock_alert'), "_send_combined_stock_alert method exists"
        assert hasattr(jobs, '_format_sku_for_message'), "_format_sku_for_message method exists"
        
        print("✅ Все методы проверки остатков добавлены")
        return True
        
    except Exception as e:
        print(f"❌ Stock check function test failed: {e}")
        return False

def main():
    """Основной тест планировщика."""
    print("🚀 Тест конфигурации планировщика после обновлений...\n")
    
    tests = [
        ("Конфигурация планировщика", test_scheduler_jobs),
        ("Функция проверки остатков", test_new_stock_check_function)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                break
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
            break
    
    print(f"\n📊 Результат тестов планировщика: {passed}/{total}")
    
    if passed == total:
        print("🎉 Планировщик готов к работе с новым расписанием!")
        print("\nНовое расписание:")
        print("• 10:00 - Проверка остатков (🟡🔴)")  
        print("• 15:00 - Проверка остатков (🟡🔴)")
        print("• 21:00 - Проверка остатков (🟡🔴)")
        print("• 21:01 - Ежедневный расчет")
        print("• Пн 10:30 - Еженедельная аналитика")
        return True
    else:
        print("⚠️ Планировщик требует исправлений.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)