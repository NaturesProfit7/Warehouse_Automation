#!/usr/bin/env python3
"""Тестирование различных параметров with для получения позиций заказа KeyCRM."""

import asyncio
import sys
import os
sys.path.append('src')

async def test_various_with_params():
    print('🔍 ТЕСТИРОВАНИЕ РАЗЛИЧНЫХ with ПАРАМЕТРОВ')
    print('='*60)
    
    import httpx
    from dotenv import load_dotenv
    
    load_dotenv()
    token = os.getenv('KEYCRM_API_TOKEN')
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    base_url = 'https://openapi.keycrm.app/v1'
    order_id = 4509
    
    # Различные варианты with параметров
    with_params = [
        'items',
        'orderItems', 
        'order_items',
        'products',
        'positions',
        'lines',
        'details',
        'order-items',
        'orderitems'
    ]
    
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        
        for param in with_params:
            print(f'\n🔍 Тестируем with={param}')
            try:
                response = await client.get(
                    f'/order/{order_id}', 
                    headers=headers, 
                    params={'with': param}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    order_items = data.get('order_items', [])
                    items = data.get('items', [])
                    products = data.get('products', [])
                    positions = data.get('positions', [])
                    
                    print(f'   ✅ Status: {response.status_code}')
                    print(f'   📦 order_items: {len(order_items)}')
                    print(f'   📦 items: {len(items)}')
                    print(f'   📦 products: {len(products)}')  
                    print(f'   📦 positions: {len(positions)}')
                    
                    # Если нашли товары в любом поле
                    if order_items or items or products or positions:
                        print(f'   🎉 НАЙДЕНЫ ПОЗИЦИИ С ПАРАМЕТРОМ: {param}')
                        
                        # Показываем первую позицию
                        found_items = order_items or items or products or positions
                        if found_items:
                            first_item = found_items[0]
                            print(f'   📋 Первая позиция: {first_item}')
                    
                else:
                    print(f'   ❌ Status: {response.status_code} - {response.text[:100]}')
                    
            except Exception as e:
                print(f'   ❌ Ошибка: {str(e)[:100]}')
        
        print(f'\n🔍 ДОПОЛНИТЕЛЬНО: Тестируем multiple параметры')
        try:
            response = await client.get(
                f'/order/{order_id}', 
                headers=headers, 
                params={'with': 'items,products,client,source'}
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f'   ✅ Multiple with params - Status: {response.status_code}')
                print(f'   📦 order_items: {len(data.get("order_items", []))}')
                print(f'   📦 items: {len(data.get("items", []))}')
                print(f'   📦 products: {len(data.get("products", []))}')
                
                # Показываем все доступные ключи
                print(f'   🔑 Все ключи: {list(data.keys())[:10]}...')
            else:
                print(f'   ❌ Multiple params failed: {response.status_code}')
                
        except Exception as e:
            print(f'   ❌ Ошибка multiple params: {e}')

if __name__ == "__main__":
    asyncio.run(test_various_with_params())