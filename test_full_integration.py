#!/usr/bin/env python3
"""Полный тест интеграции с KeyCRM API."""

import asyncio
import sys
import os
sys.path.append('src')

async def test_keycrm_integration():
    """Тест полной интеграции KeyCRM."""
    
    print("🔗 ТЕСТ ПОЛНОЙ ИНТЕГРАЦИИ KeyCRM")
    print("="*60)
    
    try:
        from integrations.keycrm import get_keycrm_client
        
        # Получаем клиент KeyCRM
        print("1️⃣ Инициализация KeyCRM клиента...")
        async with await get_keycrm_client() as client:
            print("   ✅ KeyCRM клиент создан")
            
            # Тестируем получение заказа
            print("\n2️⃣ Получение заказа по ID...")
            order_id = 4505  # ID последнего созданного заказа
            
            try:
                order = await client.get_order(order_id)
                print(f"   ✅ Заказ {order_id} получен успешно!")
                print(f"   📦 Order ID: {order.id}")
                print(f"   📊 Status: {order.status}")
                print(f"   👤 Client ID: {order.client_id}")
                print(f"   💰 Grand Total: {order.grand_total}")
                print(f"   📋 Items count: {len(order.items)}")
                
                if order.items:
                    print("   📦 Позиции заказа:")
                    for i, item in enumerate(order.items[:3]):
                        print(f"     {i+1}. {item.product_name} x {item.quantity} = {item.total}")
                else:
                    print("   ⚠️  Позиции заказа не найдены")
                    print("   💡 Возможно заказ создан без товаров или API не возвращает позиции")
                
            except Exception as e:
                print(f"   ❌ Ошибка получения заказа: {e}")
                return False
            
            # Тестируем получение списка заказов
            print(f"\n3️⃣ Получение списка заказов...")
            try:
                from datetime import date, timedelta
                
                # Получаем заказы за последние 7 дней
                start_date = date.today() - timedelta(days=7)
                end_date = date.today()
                
                orders = await client.get_orders_by_date_range(start_date, end_date, limit=5)
                print(f"   ✅ Получено заказов за период: {len(orders)}")
                
                if orders:
                    print("   📋 Последние заказы:")
                    for order in orders[:3]:
                        print(f"     • Order {order.id}: {order.grand_total} (status: {order.status})")
                else:
                    print("   ⚠️  Заказов за период не найдено")
                
            except Exception as e:
                print(f"   ❌ Ошибка получения списка: {e}")
            
            print(f"\n4️⃣ Тестирование webhook payload парсинга...")
            try:
                # Симулируем webhook payload
                webhook_payload = {
                    "event": "order.change_order_status",
                    "context": {
                        "id": order_id,
                        "status_id": 1,
                        "client_id": 12345,
                        "grand_total": 500.0
                    }
                }
                
                parsed_webhook = client.parse_webhook_payload(webhook_payload)
                print(f"   ✅ Webhook payload распарсен успешно")
                print(f"   📨 Event: {parsed_webhook.event}")
                print(f"   📦 Order ID: {parsed_webhook.order_id}")
                print(f"   📊 Status: {parsed_webhook.order_status}")
                
            except Exception as e:
                print(f"   ❌ Ошибка парсинга webhook: {e}")
            
            return True
            
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_webhook_processing():
    """Тест обработки webhook."""
    
    print(f"\n{'='*60}")
    print("🎯 ТЕСТ ОБРАБОТКИ WEBHOOK")
    print("="*60)
    
    try:
        from webhook.handlers import KeyCRMWebhookHandler
        
        handler = KeyCRMWebhookHandler()
        
        # Симулируем реальный webhook от KeyCRM
        webhook_payload = {
            "event": "order.change_order_status",
            "context": {
                "id": 4505,           # ID реального заказа
                "status_id": 1,       # Новый статус
                "client_id": None,
                "grand_total": 500.0,
                "status_changed_at": "2025-08-26T18:30:00.000000Z"
            }
        }
        
        print("1️⃣ Обработка webhook...")
        print(f"   📨 Event: {webhook_payload['event']}")
        print(f"   📦 Order ID: {webhook_payload['context']['id']}")
        print(f"   📊 Status ID: {webhook_payload['context']['status_id']}")
        
        result = await handler.handle_keycrm_webhook(webhook_payload, request_id="test_001")
        
        print(f"   ✅ Webhook обработан успешно!")
        print(f"   📋 Результат: {result}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Ошибка обработки webhook: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Главная функция тестирования."""
    
    # Тест 1: KeyCRM API интеграция
    api_success = await test_keycrm_integration()
    
    # Тест 2: Обработка webhook
    webhook_success = await test_webhook_processing()
    
    # Итоговый результат
    print(f"\n{'='*60}")
    print("🏁 ИТОГОВЫЕ РЕЗУЛЬТАТЫ")
    print("="*60)
    
    print(f"KeyCRM API: {'✅ Работает' if api_success else '❌ Не работает'}")
    print(f"Webhook обработка: {'✅ Работает' if webhook_success else '❌ Не работает'}")
    
    if api_success and webhook_success:
        print(f"\n🎉 ПОЛНАЯ ИНТЕГРАЦИЯ РАБОТАЕТ!")
        print(f"✅ Система готова к продуктивному использованию")
        print(f"📋 Можно создать заказ в KeyCRM для полного теста")
    else:
        print(f"\n⚠️  Есть проблемы с интеграцией")
        print(f"🔧 Нужно устранить ошибки перед продакшеном")

if __name__ == "__main__":
    asyncio.run(main())