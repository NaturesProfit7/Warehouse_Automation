#!/usr/bin/env python3
"""Тест KeyCRM OpenAPI с правильным endpoint."""

import asyncio
import httpx
import os
from dotenv import load_dotenv

async def test_keycrm_openapi():
    """Тест KeyCRM OpenAPI с официальной документацией."""
    
    load_dotenv()
    api_token = os.getenv("KEYCRM_API_TOKEN")
    
    print("🔍 ТЕСТИРОВАНИЕ KeyCRM OpenAPI")
    print("="*60)
    print("Согласно документации:")
    print("• URL: https://openapi.keycrm.app")
    print("• Авторизация: Bearer + APIkey")
    print("• Лимит: 60 запросов/минуту")
    print("• Формат времени: UTC (GMT+0)")
    print(f"• Токен: {api_token[:15]}...")
    
    # Настройка клиента согласно документации
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    base_url = "https://openapi.keycrm.app"
    
    # Тестируем разные endpoints
    test_endpoints = [
        {
            "name": "Получение заказа по ID",
            "path": "/orders/4505",  # Последний созданный заказ
            "method": "GET"
        },
        {
            "name": "Список заказов",
            "path": "/orders", 
            "method": "GET",
            "params": {"limit": 5}
        }
    ]
    
    async with httpx.AsyncClient(base_url=base_url, timeout=15.0) as client:
        for test in test_endpoints:
            print(f"\n🧪 {test['name']}")
            print(f"URL: {base_url}{test['path']}")
            
            try:
                if test['method'] == 'GET':
                    response = await client.get(
                        test['path'],
                        headers=headers,
                        params=test.get('params', {})
                    )
                
                print(f"Статус: {response.status_code}")
                print(f"Content-Type: {response.headers.get('Content-Type', 'Не указан')}")
                print(f"Размер ответа: {len(response.content)} bytes")
                
                if response.status_code == 200:
                    content_type = response.headers.get('Content-Type', '')
                    if 'application/json' in content_type:
                        try:
                            data = response.json()
                            print(f"✅ УСПЕХ! JSON данные получены")
                            
                            if isinstance(data, dict):
                                print(f"Ключи: {list(data.keys())}")
                                
                                # Если это заказ
                                if 'id' in data:
                                    print(f"📦 Order ID: {data.get('id')}")
                                    print(f"📊 Status: {data.get('status', 'N/A')}")
                                    print(f"👤 Client ID: {data.get('client_id', 'N/A')}")
                                    print(f"💰 Total: {data.get('grand_total', 'N/A')}")
                                    
                                    # Проверяем позиции заказа
                                    items = data.get('order_items', [])
                                    if items:
                                        print(f"📋 Позиций в заказе: {len(items)}")
                                        for i, item in enumerate(items[:2]):  # Показываем первые 2
                                            print(f"  {i+1}. {item.get('product_name', 'N/A')} x {item.get('quantity', 0)}")
                                
                                # Если это список заказов
                                elif 'data' in data or isinstance(data, list):
                                    orders = data.get('data', data) if isinstance(data, dict) else data
                                    if isinstance(orders, list):
                                        print(f"📋 Заказов в списке: {len(orders)}")
                                        for order in orders[:2]:  # Показываем первые 2
                                            print(f"  • Order {order.get('id')}: {order.get('grand_total')} ({order.get('status')})")
                            
                            print(f"🎉 API РАБОТАЕТ! Проблема решена!")
                            return True
                            
                        except Exception as e:
                            print(f"❌ Ошибка парсинга JSON: {e}")
                            print(f"Ответ: {response.text[:200]}...")
                    else:
                        print(f"❌ Не JSON ответ: {content_type}")
                        print(f"Ответ: {response.text[:200]}...")
                
                elif response.status_code == 401:
                    print(f"🔑 ОШИБКА АВТОРИЗАЦИИ")
                    print("Возможные причины:")
                    print("• Неверный API токен")
                    print("• Токен истек") 
                    print("• API доступ не активирован")
                    
                elif response.status_code == 403:
                    print(f"🚫 ДОСТУП ЗАПРЕЩЕН")
                    print("Возможные причины:")
                    print("• У токена нет прав на чтение заказов")
                    print("• Превышен лимит запросов (60/мин)")
                    
                elif response.status_code == 404:
                    print(f"❌ НЕ НАЙДЕНО")
                    if "orders/" in test['path']:
                        print("• Заказ с таким ID не существует")
                    else:
                        print("• Endpoint не найден")
                
                else:
                    print(f"❓ Неожиданный статус: {response.status_code}")
                    print(f"Ответ: {response.text[:200]}...")
                
            except Exception as e:
                print(f"❌ ОШИБКА ЗАПРОСА: {e}")
    
    return False

async def main():
    """Основная функция."""
    
    success = await test_keycrm_openapi()
    
    print(f"\n{'='*60}")
    if success:
        print("🎉 KeyCRM OpenAPI РАБОТАЕТ!")
        print("✅ Можно переходить к полному тестированию системы")
        print("✅ Webhook + API интеграция готова к работе")
    else:
        print("❌ KeyCRM OpenAPI не работает")
        print("🔧 Нужно проверить токен в админке KeyCRM")
    print(f"{'='*60}")

if __name__ == "__main__":
    asyncio.run(main())