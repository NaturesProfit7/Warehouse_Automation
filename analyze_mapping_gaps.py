#!/usr/bin/env python3
"""Скрипт для анализа пропусков в маппинге KeyCRM продуктов."""

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta

from src.integrations.keycrm import KeyCRMClient
from src.integrations.sheets import get_sheets_client
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def analyze_mapping_gaps(days_back: int = 30) -> None:
    """
    Анализирует пропуски в маппинге продуктов KeyCRM.
    
    Args:
        days_back: Количество дней назад для анализа
    """
    try:
        logger.info(f"Analyzing product mapping gaps for last {days_back} days...")
        
        # Инициализируем клиенты
        keycrm_client = KeyCRMClient()
        sheets_client = get_sheets_client()
        
        # Получаем существующие маппинги
        product_mappings = sheets_client.get_product_mappings()
        mapping_dict = {}
        for mapping in product_mappings:
            key = (mapping.product_name, mapping.size_property, mapping.metal_color)
            mapping_dict[key] = mapping
        
        print(f"\n📊 Существующие маппинги ({len(product_mappings)}):")
        for i, mapping in enumerate(product_mappings, 1):
            print(f"  {i}. '{mapping.product_name}' | '{mapping.size_property}' | '{mapping.metal_color}' → {mapping.blank_sku}")
        
        # Получаем заказы из KeyCRM
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        all_orders = []
        page = 1
        max_pages = 10
        
        while page <= max_pages:
            params = {
                "start_date": start_date.date().isoformat(),
                "end_date": end_date.date().isoformat(),
                "page": page,
                "limit": 100
            }
            
            logger.info(f"Fetching page {page}...")
            response = await keycrm_client.client.get("/order", params=params)
            response.raise_for_status()
            
            data = response.json()
            orders_data = data.get("data", [])
            
            if not orders_data:
                break
                
            page_orders = []
            for order_data in orders_data:
                order = keycrm_client._parse_order_response(order_data)
                page_orders.append(order)
            
            all_orders.extend(page_orders)
            
            if not data.get("next_page_url"):
                break
                
            page += 1
        
        print(f"\n📦 Получено {len(all_orders)} заказов")
        
        # Анализируем продукты
        mapped_products = defaultdict(int)
        unmapped_products = defaultdict(int)
        cancelled_orders = 0
        
        for order_preview in all_orders:
            order_status = order_preview.status.lower()
            
            # Пропускаем отмененные заказы
            if order_status in ["отменен", "отменён", "отмена", "cancelled"]:
                cancelled_orders += 1
                continue
            
            try:
                full_order = await keycrm_client.get_order(order_preview.id)
                order_items = full_order.items
                
                for item in order_items:
                    product_name = item.product_name.strip()
                    quantity = item.quantity
                    
                    # Получаем свойства товара
                    properties = item.properties
                    size_property = ""
                    metal_color = ""
                    
                    for prop_name, prop_value in properties.items():
                        prop_name = prop_name.lower()
                        if "розмір" in prop_name or "размер" in prop_name:
                            size_property = prop_value
                        elif "колір" in prop_name or "цвет" in prop_name:
                            metal_color = prop_value
                    
                    # Проверяем маппинг
                    mapping_key = (product_name, size_property, metal_color)
                    
                    if mapping_key in mapping_dict and mapping_dict[mapping_key].active:
                        mapped_products[mapping_key] += quantity
                    else:
                        # Пытаемся найти частичное совпадение по имени
                        partial_match = False
                        for key, map_item in mapping_dict.items():
                            if key[0] == product_name and map_item.active:
                                mapped_products[key] += quantity
                                partial_match = True
                                break
                        
                        if not partial_match:
                            unmapped_products[mapping_key] += quantity
                            
            except Exception as e:
                logger.warning(f"Failed to fetch order {order_preview.id}: {e}")
                continue
        
        # Выводим результаты
        print(f"\n✅ СОПОСТАВЛЕННЫЕ ПРОДУКТЫ ({len(mapped_products)}):")
        for (name, size, color), qty in sorted(mapped_products.items(), key=lambda x: x[1], reverse=True):
            mapping = mapping_dict.get((name, size, color))
            sku = mapping.blank_sku if mapping else "PARTIAL_MATCH"
            print(f"  {qty:3d}x '{name}' | '{size}' | '{color}' → {sku}")
        
        print(f"\n❌ НЕСОПОСТАВЛЕННЫЕ ПРОДУКТЫ ({len(unmapped_products)}):")
        unmapped_sorted = sorted(unmapped_products.items(), key=lambda x: x[1], reverse=True)
        
        for (name, size, color), qty in unmapped_sorted:
            print(f"  {qty:3d}x '{name}' | '{size}' | '{color}'")
        
        # Статистика
        total_mapped_qty = sum(mapped_products.values())
        total_unmapped_qty = sum(unmapped_products.values())
        total_qty = total_mapped_qty + total_unmapped_qty
        
        print(f"\n📈 СТАТИСТИКА:")
        print(f"  Всего заказов: {len(all_orders)}")
        print(f"  Отменено: {cancelled_orders}")
        print(f"  Всего товаров: {total_qty} шт")
        print(f"  Сопоставлено: {total_mapped_qty} шт ({total_mapped_qty/total_qty*100:.1f}%)")
        print(f"  Не сопоставлено: {total_unmapped_qty} шт ({total_unmapped_qty/total_qty*100:.1f}%)")
        
        # Анализ адресников
        addressnik_variants = {}
        for (name, size, color), qty in unmapped_products.items():
            if "адресник" in name.lower():
                addressnik_variants[(name, size, color)] = qty
        
        if addressnik_variants:
            print(f"\n🏷️  НЕСОПОСТАВЛЕННЫЕ АДРЕСНИКИ ({len(addressnik_variants)} вариантов):")
            for (name, size, color), qty in sorted(addressnik_variants.items(), key=lambda x: x[1], reverse=True):
                print(f"  {qty:3d}x '{name}' | '{size}' | '{color}'")
        
        # Предложения по добавлению маппингов
        print(f"\n💡 РЕКОМЕНДАЦИИ:")
        if unmapped_products:
            top_unmapped = sorted(unmapped_products.items(), key=lambda x: x[1], reverse=True)[:10]
            print(f"  Топ-10 несопоставленных товаров для добавления в маппинги:")
            for i, ((name, size, color), qty) in enumerate(top_unmapped, 1):
                print(f"    {i}. {qty:3d}x '{name}' | '{size}' | '{color}'")
        
        await keycrm_client.close()
        
    except Exception as e:
        logger.error(f"Failed to analyze mapping gaps: {e}")
        raise


if __name__ == "__main__":
    try:
        days_back = int(input("Количество дней для анализа (по умолчанию 30): ") or "30")
        asyncio.run(analyze_mapping_gaps(days_back))
    except KeyboardInterrupt:
        logger.info("Analysis cancelled by user")
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        import sys
        sys.exit(1)