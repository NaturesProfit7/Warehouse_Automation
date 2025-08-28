#!/usr/bin/env python3
"""Диагностика заказа 4509 от KeyCRM."""

import asyncio
import sys
import os
sys.path.append('src')

async def debug_order_4509():
    print('🔍 ДЕТАЛЬНАЯ ДИАГНОСТИКА ЗАКАЗА 4509')
    print('='*60)
    
    # Прямой HTTP запрос к KeyCRM API
    import httpx
    from dotenv import load_dotenv
    
    load_dotenv()
    token = os.getenv('KEYCRM_API_TOKEN')
    
    print(f'🔑 API Token: {token[:20]}...')
    print()
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    base_url = 'https://openapi.keycrm.app/v1'
    
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        # Запрос заказа БЕЗ параметра with
        print('1️⃣ ЗАПРОС БЕЗ ПАРАМЕТРА with=items')
        try:
            response = await client.get(f'/order/4509', headers=headers)
            print(f'Status Code: {response.status_code}')
            
            if response.status_code == 200:
                data = response.json()
                print('📋 Основные поля заказа:')
                print(f'   ID: {data.get("id")}')
                print(f'   Status ID: {data.get("status_id")}')
                print(f'   Grand Total: {data.get("grand_total")}')
                print(f'   Products Total: {data.get("products_total")}')
                print(f'   Client ID: {data.get("client_id")}')
                print()
                
                # Проверим есть ли поле order_items
                order_items = data.get('order_items', [])
                print(f'📦 order_items field: {len(order_items)} items')
                
                if order_items:
                    print('   Позиции:')
                    for item in order_items:
                        print(f'     • {item.get("product_name")} x {item.get("quantity")}')
                else:
                    print('   ❌ Поле order_items пустое')
                
                # Проверим все ключи в ответе
                print(f'🔍 Все ключи в ответе: {list(data.keys())}')
            else:
                print(f'❌ Ошибка: {response.status_code}')
                print(f'Response: {response.text}')
                
        except Exception as e:
            print(f'❌ Ошибка запроса без with: {e}')
        
        print()
        print('2️⃣ ЗАПРОС С ПАРАМЕТРОМ with=items')
        try:
            response = await client.get(f'/order/4509', headers=headers, params={'with': 'items'})
            print(f'Status Code: {response.status_code}')
            
            if response.status_code == 200:
                data = response.json()
                order_items = data.get('order_items', [])
                print(f'📦 С параметром with=items: {len(order_items)} items')
                
                if order_items:
                    print('   Позиции:')
                    for item in order_items:
                        print(f'     • Product ID: {item.get("product_id")}')
                        print(f'     • Name: {item.get("product_name")}')
                        print(f'     • Quantity: {item.get("quantity")}')
                        print(f'     • Price: {item.get("price")}')
                        print()
                else:
                    print('   ❌ Всё ещё нет позиций')
            else:
                print(f'❌ Ошибка: {response.status_code}')
                print(f'Response: {response.text}')
                
        except Exception as e:
            print(f'❌ Ошибка запроса с with: {e}')

if __name__ == "__main__":
    asyncio.run(debug_order_4509())