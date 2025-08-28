#!/usr/bin/env python3
"""Диагностика проблем с KeyCRM API токеном."""

import os
import base64
import asyncio
import httpx
from dotenv import load_dotenv

def analyze_token_format():
    """Анализ формата токена."""
    load_dotenv()
    
    token = os.getenv("KEYCRM_API_TOKEN")
    print("🔍 АНАЛИЗ API ТОКЕНА KeyCRM")
    print("="*60)
    
    print(f"Токен: {token}")
    print(f"Длина: {len(token)} символов")
    print(f"Первые 10: {token[:10]}...")
    print(f"Последние 10: ...{token[-10:]}")
    
    # Проверяем является ли токен base64
    try:
        decoded = base64.b64decode(token)
        print(f"✅ Это Base64 строка")
        print(f"Декодированное значение: {decoded.decode('utf-8', errors='ignore')}")
    except:
        print(f"❌ Не Base64 строка")
    
    # Проверяем является ли токен hex
    try:
        bytes.fromhex(token)
        print(f"✅ Это HEX строка")
    except:
        print(f"❌ Не HEX строка")
    
    # Анализ символов
    has_upper = any(c.isupper() for c in token)
    has_lower = any(c.islower() for c in token)
    has_digits = any(c.isdigit() for c in token)
    has_special = any(not c.isalnum() for c in token)
    
    print(f"\nСостав токена:")
    print(f"  Заглавные буквы: {'✅' if has_upper else '❌'}")
    print(f"  Строчные буквы: {'✅' if has_lower else '❌'}")
    print(f"  Цифры: {'✅' if has_digits else '❌'}")
    print(f"  Спец. символы: {'✅' if has_special else '❌'}")

async def test_different_approaches():
    """Тест различных подходов к API."""
    
    load_dotenv()
    token = os.getenv("KEYCRM_API_TOKEN")
    
    print(f"\n🧪 ТЕСТИРОВАНИЕ РАЗЛИЧНЫХ ПОДХОДОВ")
    print("="*60)
    
    # Возможные варианты проблемы
    test_scenarios = [
        {
            "name": "1. Проверка доступности API вообще",
            "url": "https://api.keycrm.app",
            "method": "GET",
            "headers": {},
            "description": "Проверяем отвечает ли API сервер"
        },
        {
            "name": "2. Проверка без токена",
            "url": "https://api.keycrm.app/orders",
            "method": "GET", 
            "headers": {"Content-Type": "application/json"},
            "description": "Проверяем что возвращает API без аутентификации"
        },
        {
            "name": "3. Возможно нужна версия API",
            "url": "https://api.keycrm.app/v1/orders",
            "method": "GET",
            "headers": {"Authorization": f"Bearer {token}"},
            "description": "Проверяем с версией v1"
        },
        {
            "name": "4. Возможно это openapi поддомен",
            "url": "https://openapi.keycrm.app/orders",
            "method": "GET", 
            "headers": {"Authorization": f"Bearer {token}"},
            "description": "Проверяем поддомен openapi"
        },
        {
            "name": "5. Проверяем с User-Agent",
            "url": "https://api.keycrm.app/orders",
            "method": "GET",
            "headers": {
                "Authorization": f"Bearer {token}",
                "User-Agent": "KeyCRM-Integration/1.0"
            },
            "description": "Добавляем User-Agent"
        }
    ]
    
    for scenario in test_scenarios:
        print(f"\n{scenario['name']}")
        print(f"URL: {scenario['url']}")
        print(f"Описание: {scenario['description']}")
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.request(
                    scenario['method'],
                    scenario['url'], 
                    headers=scenario['headers']
                )
                
                print(f"  Статус: {response.status_code}")
                print(f"  Content-Type: {response.headers.get('Content-Type', 'Не указан')}")
                
                # Анализ ответа
                if response.status_code == 401:
                    print(f"  🔑 ТРЕБУЕТСЯ АУТЕНТИФИКАЦИЯ")
                elif response.status_code == 403:
                    print(f"  🚫 ДОСТУП ЗАПРЕЩЕН (токен неверный)")
                elif response.status_code == 404:
                    print(f"  ❌ ENDPOINT НЕ НАЙДЕН")
                elif "application/json" in response.headers.get('Content-Type', ''):
                    print(f"  ✅ JSON ОТВЕТ!")
                    try:
                        data = response.json()
                        print(f"  Данные: {list(data.keys()) if isinstance(data, dict) else data}")
                    except:
                        print(f"  ❌ Ошибка парсинга JSON")
                else:
                    print(f"  📄 HTML ответ (веб-интерфейс)")
                    
        except Exception as e:
            print(f"  ❌ ОШИБКА: {e}")

def check_token_source():
    """Проверка откуда взят токен."""
    
    print(f"\n📋 ГДЕ ВЗЯТЬ ПРАВИЛЬНЫЙ API ТОКЕН")
    print("="*60)
    
    print("В KeyCRM API токен обычно находится в:")
    print("1. 🏢 Настройки → Интеграции → API")
    print("2. 🔧 Настройки → Для разработчиков → API ключи")
    print("3. 👤 Профиль → API токены")
    print("4. ⚙️  Администрирование → API доступ")
    
    print(f"\n❗ ВАЖНЫЕ МОМЕНТЫ:")
    print("• Токен должен быть активным")
    print("• У токена должны быть права на чтение заказов") 
    print("• Возможно API требует активации в админке")
    print("• Возможно есть ограничения по IP или домену")
    
    print(f"\n🔍 ЧТО ПРОВЕРИТЬ В KeyCRM:")
    print("1. Зайти в админ панель KeyCRM")
    print("2. Найти раздел API/Интеграции")
    print("3. Проверить статус API (включен/выключен)")
    print("4. Проверить права токена")
    print("5. При необходимости создать новый токен")
    print("6. Проверить есть ли ограничения по IP")

async def main():
    """Основная функция диагностики."""
    
    analyze_token_format()
    await test_different_approaches() 
    check_token_source()
    
    print(f"\n🎯 ВЫВОД")
    print("="*60)
    print("Наиболее вероятные причины:")
    print("1. 🔑 API токен неверный или истек")
    print("2. ⚡ API отключен в настройках KeyCRM")
    print("3. 🔒 У токена нет прав на чтение заказов")
    print("4. 🌐 Неправильный базовый URL для API")
    print("5. 🚫 Ограничения по IP/домену")
    
    print(f"\n💡 РЕКОМЕНДУЕМЫЕ ДЕЙСТВИЯ:")
    print("1. Проверить настройки API в KeyCRM админке")
    print("2. Создать новый API токен")
    print("3. Убедиться что API включен")
    print("4. Проверить права доступа токена")

if __name__ == "__main__":
    asyncio.run(main())