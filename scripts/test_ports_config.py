#!/usr/bin/env python3
"""Тест новой конфигурации портов."""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_ports_configuration():
    """Тест конфигурации портов после изменений."""
    print("🔌 Тестирую конфигурацию портов...")
    
    try:
        # Проверяем main_with_scheduler.py
        with open('main_with_scheduler.py', 'r') as f:
            content = f.read()
            
        if '9001' in content and '8000' not in content:
            print("✅ main_with_scheduler.py: порт изменен на 9001")
        else:
            print("❌ main_with_scheduler.py: порт не изменен")
            return False
            
        # Проверяем webhook app
        with open('src/webhook/app.py', 'r') as f:
            content = f.read()
            
        if 'port=9000' in content:
            print("✅ src/webhook/app.py: порт изменен на 9000")
        else:
            print("❌ src/webhook/app.py: порт не изменен")
            return False
            
        # Проверяем docker-compose.yml
        with open('docker-compose.yml', 'r') as f:
            content = f.read()
            
        if '9000:9000' in content and '9001:9001' in content:
            print("✅ docker-compose.yml: порты 9000 и 9001 настроены")
        else:
            print("❌ docker-compose.yml: порты не настроены")
            return False
            
        # Проверяем что старые порты не используются
        if ':8000' not in content:
            print("✅ docker-compose.yml: старый порт 8000 удален")
        else:
            print("❌ docker-compose.yml: старый порт 8000 остался")
            return False
            
        print("\n✅ Все порты настроены правильно!")
        print("• Telegram bot health check: :9001")
        print("• KeyCRM webhook server: :9000")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка проверки портов: {e}")
        return False

def test_docker_compose_structure():
    """Тест структуры docker-compose.yml."""
    print("\n🐳 Тестирую структуру docker-compose.yml...")
    
    try:
        import yaml
        
        with open('docker-compose.yml', 'r') as f:
            config = yaml.safe_load(f)
            
        services = config.get('services', {})
        
        # Проверяем наличие двух сервисов
        if 'telegram-bot' in services and 'webhook-server' in services:
            print("✅ Два сервиса созданы: telegram-bot, webhook-server")
        else:
            print("❌ Не все сервисы найдены")
            return False
            
        # Проверяем команды запуска
        telegram_cmd = services['telegram-bot'].get('command', [])
        webhook_cmd = services['webhook-server'].get('command', [])
        
        if 'main_with_scheduler.py' in str(telegram_cmd):
            print("✅ telegram-bot: команда запуска корректна")
        else:
            print("❌ telegram-bot: неверная команда запуска")
            return False
            
        if 'uvicorn' in str(webhook_cmd) and 'src.webhook.app:app' in str(webhook_cmd):
            print("✅ webhook-server: команда запуска корректна")
        else:
            print("❌ webhook-server: неверная команда запуска")
            return False
            
        print("✅ Структура docker-compose.yml корректна!")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка проверки docker-compose: {e}")
        return False

def main():
    """Основной тест новой конфигурации."""
    print("🚀 Тест новой конфигурации портов и сервисов...\n")
    
    tests = [
        ("Конфигурация портов", test_ports_configuration),
        ("Структура Docker Compose", test_docker_compose_structure)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
    
    print(f"\n📊 Результат тестов: {passed}/{total}")
    
    if passed == total:
        print("🎉 Конфигурация готова к деплою!")
        print("\nНовая архитектура:")
        print("• telegram-bot   :9001 (health check)")
        print("• webhook-server :9000 (KeyCRM webhooks)")
        print("\nКоманды деплоя:")
        print("docker-compose up -d --build")
        print("docker-compose logs -f telegram-bot")
        print("docker-compose logs -f webhook-server")
        return True
    else:
        print("⚠️ Конфигурация требует исправлений.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)