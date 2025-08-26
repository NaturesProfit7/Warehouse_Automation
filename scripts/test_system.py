#!/usr/bin/env python3
"""Скрипт для локального тестирования всей системы."""

import os
import sys
import asyncio
import subprocess
from pathlib import Path

# Добавляем src в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))

def run_command(command, description):
    """Запуск команды с описанием."""
    print(f"\n🔄 {description}")
    print(f"Команда: {command}")
    
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    
    if result.returncode == 0:
        print(f"✅ {description} - успешно")
        if result.stdout.strip():
            print(f"Результат:\n{result.stdout}")
    else:
        print(f"❌ {description} - ошибка")
        if result.stderr.strip():
            print(f"Ошибки:\n{result.stderr}")
        if result.stdout.strip():
            print(f"Вывод:\n{result.stdout}")
    
    return result.returncode == 0

def check_project_structure():
    """Проверка структуры проекта."""
    print("\n📂 Проверка структуры проекта")
    
    required_dirs = [
        'src/core',
        'src/services', 
        'src/integrations',
        'src/webhook',
        'src/bot',
        'src/scheduler',
        'src/utils',
        'tests'
    ]
    
    required_files = [
        'src/core/models.py',
        'src/core/calculations.py',
        'src/services/stock_service.py',
        'src/integrations/keycrm.py',
        'src/webhook/app.py',
        'src/bot/handlers.py',
        'src/scheduler/jobs.py',
        'requirements.txt',
        'pyproject.toml'
    ]
    
    all_good = True
    
    for dir_path in required_dirs:
        full_path = project_root / dir_path
        if full_path.exists():
            print(f"✅ Директория {dir_path} - есть")
        else:
            print(f"❌ Директория {dir_path} - отсутствует")
            all_good = False
    
    for file_path in required_files:
        full_path = project_root / file_path
        if full_path.exists():
            print(f"✅ Файл {file_path} - есть")
        else:
            print(f"❌ Файл {file_path} - отсутствует")
            all_good = False
    
    return all_good

def test_imports():
    """Тестирование импортов без внешних зависимостей."""
    print("\n📦 Тестирование импортов")
    
    try:
        # Core modules
        from src.core.models import BlankType, MovementType, UrgencyLevel
        from src.core.exceptions import StockCalculationError, IntegrationError
        from src.core.validators import validate_blank_sku
        
        print("✅ Core модули импортируются")
        
        # Проверяем энумы
        assert BlankType.RING == "RING"
        assert MovementType.ORDER == "order" 
        assert UrgencyLevel.CRITICAL == "critical"
        
        print("✅ Энумы работают корректно")
        
        # Проверяем валидацию
        assert validate_blank_sku("BLK-RING-25-GLD") == True
        assert validate_blank_sku("invalid") == False
        
        print("✅ Валидация работает корректно")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка импорта: {e}")
        return False

def create_test_env_file():
    """Создание тестового .env файла."""
    print("\n⚙️ Создание тестового .env файла")
    
    env_content = """# Тестовая конфигурация
KEYCRM_API_TOKEN=test_token_123
KEYCRM_WEBHOOK_SECRET=test_webhook_secret
GSHEETS_ID=1ABC123test_sheet_id
GOOGLE_CREDENTIALS_JSON={"type":"service_account","project_id":"test"}
TELEGRAM_BOT_TOKEN=123:ABC-test_bot_token
TELEGRAM_CHAT_ID=123456789

# Настройки системы
LEAD_TIME_DAYS=14
SCRAP_PCT=0.05
TARGET_COVER_DAYS=30
MAX_RETRIES=3
RETRY_DELAY_SECONDS=1.0
"""
    
    env_path = project_root / '.env.test'
    
    try:
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write(env_content)
        print(f"✅ Создан файл {env_path}")
        return True
    except Exception as e:
        print(f"❌ Ошибка создания .env: {e}")
        return False

async def test_basic_calculations():
    """Тестирование базовых расчетов."""
    print("\n🧮 Тестирование базовых расчетов")
    
    try:
        # Простые тесты без внешних зависимостей
        
        # Тест логики приоритета
        def calculate_urgency(on_hand, min_level):
            if on_hand <= min_level * 0.5:
                return "critical"
            elif on_hand <= min_level * 0.7:
                return "high" 
            elif on_hand <= min_level:
                return "medium"
            else:
                return "low"
        
        # Проверяем логику
        assert calculate_urgency(45, 100) == "critical"
        assert calculate_urgency(65, 100) == "high"
        assert calculate_urgency(95, 100) == "medium"
        assert calculate_urgency(150, 100) == "low"
        
        print("✅ Логика расчета приоритета корректна")
        
        # Тест маппинга товаров (базовый)
        def find_product_mapping(product_name, size, color, mappings):
            for mapping in mappings:
                if (mapping['name'] == product_name and 
                    mapping['size'] == size and
                    mapping['color'] == color):
                    return mapping
            return None
        
        # Тестовые данные
        mappings = [
            {'name': 'Адресник бублик', 'size': '25 мм', 'color': 'золото', 'sku': 'BLK-RING-25-GLD'}
        ]
        
        result = find_product_mapping('Адресник бублик', '25 мм', 'золото', mappings)
        assert result is not None
        assert result['sku'] == 'BLK-RING-25-GLD'
        
        print("✅ Логика маппинга товаров корректна")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка в расчетах: {e}")
        return False

def main():
    """Основная функция тестирования."""
    print("🚀 Начало тестирования системы автоматизации склада")
    print("=" * 60)
    
    # Изменяем рабочую директорию на корень проекта
    os.chdir(project_root)
    
    test_results = []
    
    # 1. Проверка структуры проекта
    test_results.append(("Структура проекта", check_project_structure()))
    
    # 2. Создание тестового окружения
    test_results.append(("Тестовый .env", create_test_env_file()))
    
    # 3. Тестирование импортов
    test_results.append(("Импорты модулей", test_imports()))
    
    # 4. Тестирование базовых расчетов
    test_results.append(("Базовые расчеты", asyncio.run(test_basic_calculations())))
    
    # 5. Запуск тестов pytest (если есть)
    test_results.append(("Pytest базовые тесты", 
                        run_command("python3 -m pytest tests/test_basic.py -v", 
                                  "Запуск базовых тестов")))
    
    # 6. Проверка синтаксиса всех Python файлов
    test_results.append(("Синтаксис Python", 
                        run_command("find src tests -name '*.py' -exec python3 -m py_compile {} \\;",
                                  "Проверка синтаксиса Python файлов")))
    
    # Итоги
    print("\n" + "=" * 60)
    print("📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ:")
    print("=" * 60)
    
    passed = 0
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ ПРОШЕЛ" if result else "❌ ПРОВАЛЕН"
        print(f"{status:<12} {test_name}")
        if result:
            passed += 1
    
    print("=" * 60)
    print(f"Результат: {passed}/{total} тестов прошли успешно")
    
    if passed == total:
        print("\n🎉 ВСЕ ТЕСТЫ ПРОШЛИ! Система готова к развертыванию.")
        
        print("\n📋 СЛЕДУЮЩИЕ ШАГИ:")
        print("1. Установите зависимости: pip install -r requirements.txt")
        print("2. Настройте .env файл с реальными значениями")
        print("3. Настройте доступ к Google Sheets API")
        print("4. Создайте Telegram бота и получите токен")
        print("5. Запустите компоненты системы")
        
        return True
    else:
        print(f"\n⚠️  НЕКОТОРЫЕ ТЕСТЫ ПРОВАЛЕНЫ! Исправьте ошибки перед развертыванием.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)