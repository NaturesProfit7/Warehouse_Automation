#!/usr/bin/env python3
"""Тест исправленного KeyCRM клиента."""

import asyncio
import sys
import os
sys.path.append('src')

async def test_fixed_keycrm():
    print('🔍 ТЕСТ ИСПРАВЛЕННОГО KeyCRM КЛИЕНТА')
    print('='*60)
    
    # Импортируем обновленный код
    from integrations.keycrm import get_keycrm_client
    
    async with await get_keycrm_client() as client:
        try:
            print('📦 Получаем заказ 4509 с исправленным кодом...')
            order = await client.get_order(4509)
            
            print(f'✅ Order ID: {order.id}')
            print(f'💰 Grand Total: {order.grand_total}')
            print(f'📊 Status: {order.status}')
            print(f'📋 Items count: {len(order.items)}')
            print()
            
            if order.items:
                print('🎉 ТОВАРЫ НАЙДЕНЫ!')
                for i, item in enumerate(order.items, 1):
                    print(f'  {i}. {item.product_name}')
                    print(f'     • Product ID: {item.product_id}')
                    print(f'     • Quantity: {item.quantity}')
                    print(f'     • Price: {item.price}')
                    print(f'     • Total: {item.total}')
                    print(f'     • Properties: {item.properties}')
                    print()
                
                print('🎯 СИСТЕМА ГОТОВА К ПОЛНОЦЕННОЙ РАБОТЕ!')
                print('✅ Товары корректно парсятся из KeyCRM API')
                
            else:
                print('❌ Товары всё ещё не найдены')
                
        except Exception as e:
            print(f'❌ Ошибка: {e}')
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_fixed_keycrm())