#!/usr/bin/env python3
"""Скрипт для импорта заказов из KeyCRM за последний месяц."""

import asyncio
from datetime import datetime, timedelta
from typing import List
from uuid import uuid4

from src.integrations.keycrm import KeyCRMClient
from src.integrations.sheets import get_sheets_client
from src.core.models import Movement, MovementType, MovementSourceType
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def import_keycrm_orders(days_back: int = 30) -> None:
    """
    Импорт заказов из KeyCRM за указанный период.
    
    Args:
        days_back: Количество дней назад для импорта
    """
    try:
        logger.info(f"Starting import of KeyCRM orders for last {days_back} days...")
        
        # Инициализируем клиенты
        keycrm_client = KeyCRMClient()
        sheets_client = get_sheets_client()
        
        # Получаем маппинги товаров
        product_mappings = sheets_client.get_product_mappings()
        mapping_dict = {}
        for mapping in product_mappings:
            key = (mapping.product_name, mapping.size_property, mapping.metal_color)
            mapping_dict[key] = mapping
        
        logger.info(f"Loaded {len(product_mappings)} product mappings")
        
        # Рассчитываем период
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        logger.info(f"Fetching orders from {start_date.date()} to {end_date.date()}")
        
        # Получаем заказы из KeyCRM с поддержкой пагинации (макс 5 страниц для теста)
        all_orders = []
        page = 1
        max_pages = 10  # Ограничиваем для теста
        
        while page <= max_pages:
            # Делаем прямой запрос с пагинацией
            params = {
                "start_date": start_date.date().isoformat(),
                "end_date": end_date.date().isoformat(),
                "page": page,
                "limit": 100  # Максимум на страницу
            }
            
            logger.info(f"Fetching page {page}...")
            response = await keycrm_client.client.get("/order", params=params)
            response.raise_for_status()
            
            data = response.json()
            orders_data = data.get("data", [])
            
            if not orders_data:
                break
                
            # Парсим заказы на текущей странице
            page_orders = []
            for order_data in orders_data:
                order = keycrm_client._parse_order_response(order_data)
                page_orders.append(order)
            
            all_orders.extend(page_orders)
            logger.info(f"Page {page}: {len(page_orders)} orders (total: {len(all_orders)})")
            
            # Проверяем есть ли следующая страница
            if not data.get("next_page_url"):
                break
                
            page += 1
            
        orders = all_orders
        
        logger.info(f"Retrieved {len(orders)} orders from KeyCRM")
        
        movements_to_add = []
        unmapped_items = []
        total_processed = 0
        cancelled_orders = 0
        
        for order_preview in orders:
            order_id = order_preview.id
            order_status = order_preview.status.lower()
            
            # Пропускаем отмененные заказы
            if order_status in ["отменен", "отменён", "отмена", "cancelled"]:
                logger.debug(f"Skipping cancelled order {order_id}")
                cancelled_orders += 1
                continue
            
            # Загружаем полный заказ с товарами
            try:
                full_order = await keycrm_client.get_order(order_id)
                order_date = full_order.created_at
                
                # Делаем дату naive если она aware
                if order_date.tzinfo is not None:
                    order_date = order_date.replace(tzinfo=None)
                
                # Обрабатываем товары в заказе
                order_items = full_order.items
                
                if not order_items:
                    logger.debug(f"Order {order_id} has no items")
                    continue
                    
            except Exception as e:
                logger.warning(f"Failed to fetch full order {order_id}: {e}")
                continue
            
            for item in order_items:
                total_processed += 1
                
                product_name = item.product_name.strip()
                quantity = item.quantity
                
                # Получаем свойства товара
                properties = item.properties
                size_property = ""
                metal_color = ""
                
                # Ищем размер и цвет в свойствах
                for prop_name, prop_value in properties.items():
                    prop_name = prop_name.lower()
                    if "розмір" in prop_name or "размер" in prop_name:
                        size_property = prop_value
                    elif "колір" in prop_name or "цвет" in prop_name:
                        metal_color = prop_value
                
                # Ищем маппинг
                mapping_key = (product_name, size_property, metal_color)
                mapping = mapping_dict.get(mapping_key)
                
                if not mapping:
                    # Пытаемся найти по названию товара
                    for key, map_item in mapping_dict.items():
                        if key[0] == product_name:
                            mapping = map_item
                            logger.warning(f"Using partial mapping for {product_name}")
                            break
                
                if mapping and mapping.active:
                    # Создаем движение расхода
                    total_qty = quantity * mapping.qty_per_unit
                    
                    movement = Movement(
                        id=uuid4(),
                        timestamp=order_date,
                        type=MovementType.ORDER,
                        source_type=MovementSourceType.KEYCRM_WEBHOOK,
                        source_id=f"IMPORT_{order_id}_{item.id}",
                        blank_sku=mapping.blank_sku,
                        qty=-total_qty,  # Отрицательное для расхода
                        balance_after=0,  # Будет пересчитан позже
                        user="KEYCRM_IMPORT",
                        note=f"Импорт заказа #{order_id}: {product_name}",
                        hash=f"import_{order_id}_{item.id}_{mapping.blank_sku}_{total_qty}"
                    )
                    
                    movements_to_add.append(movement)
                    
                else:
                    # Товар без маппинга
                    logger.warning(f"No mapping found for: {product_name} | {size_property} | {metal_color}")
                    unmapped_items.append({
                        "order_id": order_id,
                        "product_name": product_name,
                        "size_property": size_property,
                        "metal_color": metal_color,
                        "quantity": quantity
                    })
        
        logger.info(f"Processed {total_processed} order items")
        logger.info(f"Mapped movements: {len(movements_to_add)}")
        logger.info(f"Unmapped items: {len(unmapped_items)}")
        
        if movements_to_add:
            # Добавляем движения в Google Sheets
            logger.info("Adding movements to Google Sheets...")
            sheets_client.add_movements(movements_to_add)
            logger.info(f"✅ Added {len(movements_to_add)} movements to Sheets")
        
        if unmapped_items:
            logger.warning(f"⚠️  {len(unmapped_items)} items could not be mapped:")
            for item in unmapped_items[:10]:  # Показываем первые 10
                logger.warning(f"  - {item['product_name']} | {item['size_property']} | {item['metal_color']}")
            if len(unmapped_items) > 10:
                logger.warning(f"  ... and {len(unmapped_items) - 10} more")
        
        # Показываем статистику по SKU
        print("\n📊 Импортированные движения по SKU:")
        sku_totals = {}
        for movement in movements_to_add:
            sku = movement.blank_sku
            qty = abs(movement.qty)
            sku_totals[sku] = sku_totals.get(sku, 0) + qty
        
        for sku, total in sorted(sku_totals.items(), key=lambda x: x[1], reverse=True):
            print(f"  {sku}: -{total} шт")
        
        print(f"\n✅ Импорт завершен!")
        print(f"📦 Всего заказов получено: {len(orders)}")
        print(f"❌ Пропущено отмененных: {cancelled_orders}")
        print(f"📈 Всего движений: {len(movements_to_add)}")
        print(f"⚠️  Не сопоставлено: {len(unmapped_items)}")
        
    except Exception as e:
        logger.error(f"Failed to import KeyCRM orders: {e}")
        raise


if __name__ == "__main__":
    try:
        days_back = int(input("Количество дней для импорта (по умолчанию 30): ") or "30")
        asyncio.run(import_keycrm_orders(days_back))
    except KeyboardInterrupt:
        logger.info("Import cancelled by user")
    except Exception as e:
        logger.error(f"Import failed: {e}")
        import sys
        sys.exit(1)