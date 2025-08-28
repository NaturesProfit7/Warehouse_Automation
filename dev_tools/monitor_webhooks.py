#!/usr/bin/env python3
"""Мониторинг webhook событий в реальном времени."""

import asyncio
import httpx
import json
from datetime import datetime

async def monitor_webhook_server():
    """Мониторинг webhook сервера."""
    
    print("🔍 МОНИТОРИНГ WEBHOOK СОБЫТИЙ")
    print("="*50)
    print("Ожидаем webhook от KeyCRM...")
    print("Нажмите Ctrl+C для остановки")
    print()
    
    base_url = "http://localhost:8000"
    last_check = datetime.now()
    
    try:
        while True:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    # Проверяем статус сервера
                    response = await client.get(f"{base_url}/health")
                    
                    if response.status_code == 200:
                        data = response.json()
                        current_time = datetime.now().strftime("%H:%M:%S")
                        
                        print(f"\r⏰ {current_time} - Сервер активен | Status: {data.get('status', 'unknown')}", end="", flush=True)
                    else:
                        print(f"\r❌ Сервер недоступен: {response.status_code}", end="", flush=True)
                        
            except Exception as e:
                print(f"\r❌ Ошибка подключения: {str(e)[:50]}", end="", flush=True)
            
            # Ждем 2 секунды перед следующей проверкой
            await asyncio.sleep(2)
            
    except KeyboardInterrupt:
        print(f"\n\n📊 Мониторинг остановлен")

async def check_recent_orders():
    """Проверка последних заказов в KeyCRM."""
    
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    token = os.getenv('KEYCRM_API_TOKEN')
    
    if not token:
        print("❌ API токен не найден")
        return
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json'
    }
    
    base_url = 'https://openapi.keycrm.app/v1'
    
    print("\n🔍 ПРОВЕРКА ПОСЛЕДНИХ ЗАКАЗОВ KeyCRM")
    print("="*50)
    
    try:
        async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
            response = await client.get('/order', headers=headers, params={'limit': 5})
            
            if response.status_code == 200:
                data = response.json()
                orders = data.get('data', [])
                
                print(f"📋 Найдено заказов: {len(orders)}")
                print()
                
                for i, order in enumerate(orders, 1):
                    order_id = order.get('id')
                    status_id = order.get('status_id')
                    total = order.get('grand_total')
                    created = order.get('created_at', '')[:19]
                    products_total = order.get('products_total', 0)
                    
                    print(f"{i}. Order {order_id}")
                    print(f"   💰 Total: {total} | Products: {products_total}")
                    print(f"   📊 Status ID: {status_id}")
                    print(f"   📅 Created: {created}")
                    
                    # Если есть товары, покажем это
                    if products_total > 0:
                        print(f"   📦 HAS PRODUCTS - хороший кандидат для теста!")
                    else:
                        print(f"   ⚪ No products")
                    print()
                    
                return orders
            else:
                print(f"❌ Ошибка получения заказов: {response.status_code}")
                
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    
    return []

if __name__ == "__main__":
    print("🚀 ПОДГОТОВКА К ТЕСТИРОВАНИЮ НА РЕАЛЬНОМ ЗАКАЗЕ")
    print("="*60)
    
    # Сначала проверим последние заказы
    recent_orders = asyncio.run(check_recent_orders())
    
    print("📋 ИНСТРУКЦИЯ:")
    print("1. Настройте триггер в KeyCRM (если еще не сделали)")
    print("2. Создайте новый заказ с товарами")
    print("3. Запустите мониторинг: python monitor_webhooks.py")
    print("4. Следите за обработкой в реальном времени")
    print()
    print("🔗 Webhook URL для KeyCRM:")
    print("   https://witty-vans-cheer.loca.lt/webhook/keycrm")
    print()
    
    # Запуск мониторинга
    try:
        asyncio.run(monitor_webhook_server())
    except KeyboardInterrupt:
        print("Мониторинг завершен")