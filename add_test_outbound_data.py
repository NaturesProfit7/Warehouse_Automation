#!/usr/bin/env python3
"""Скрипт для добавления тестовых данных о расходах заготовок."""

from datetime import datetime, timedelta
from uuid import uuid4
import random

from src.integrations.sheets import get_sheets_client
from src.core.models import Movement, MovementType, MovementSourceType
from src.utils.logger import get_logger

logger = get_logger(__name__)


def add_test_outbound_data():
    """Добавление тестовых данных о расходах заготовок."""
    
    try:
        logger.info("Adding test outbound data...")
        
        sheets_client = get_sheets_client()
        
        # SKU для тестирования (популярные)
        test_skus = [
            "BLK-ROUND-25-GLD",  # Самый популярный
            "BLK-BONE-25-SIL",   # Второй по популярности  
            "BLK-RING-30-GLD",   # Средняя популярность
            "BLK-HEART-25-GLD",  # Средняя популярность
            "BLK-ROUND-20-SIL",  # Низкая популярность
            "BLK-CLOUD-25-SIL",  # Очень низкая популярность
        ]
        
        # Генерируем движения расхода за последние 30 дней
        movements_to_add = []
        base_date = datetime.now()
        
        for day_offset in range(30):  # 30 дней назад
            current_date = base_date - timedelta(days=day_offset)
            
            # Количество заказов в день (1-4)
            orders_per_day = random.randint(1, 4)
            
            for _ in range(orders_per_day):
                # Выбираем SKU с весами популярности
                sku_weights = [40, 25, 15, 10, 7, 3]  # Веса популярности
                sku = random.choices(test_skus, weights=sku_weights)[0]
                
                # Количество для расхода (отрицательное)
                if sku == "BLK-ROUND-25-GLD":  # Самый популярный
                    quantity = -random.randint(3, 8)
                elif sku == "BLK-BONE-25-SIL":  # Второй
                    quantity = -random.randint(2, 6) 
                elif sku in ["BLK-RING-30-GLD", "BLK-HEART-25-GLD"]:  # Средние
                    quantity = -random.randint(1, 4)
                else:  # Низкая популярность
                    quantity = -random.randint(1, 2)
                
                # Создаем движение расхода
                movement = Movement(
                    id=uuid4(),
                    timestamp=current_date,
                    type=MovementType.ORDER,
                    source_type=MovementSourceType.KEYCRM_WEBHOOK,
                    source_id=f"TEST_{random.randint(1000, 9999)}",
                    blank_sku=sku,
                    qty=quantity,  # Отрицательное для расхода
                    balance_after=0,  # Будет пересчитан
                    user="TEST_SYSTEM",
                    note=f"Тестовый заказ #{random.randint(1000, 9999)}",
                    hash=f"test_{uuid4()}"
                )
                
                movements_to_add.append(movement)
        
        logger.info(f"Generated {len(movements_to_add)} test movements")
        
        # Добавляем движения в Google Sheets
        sheets_client.add_movements(movements_to_add)
        
        logger.info("✅ Test outbound data added successfully!")
        
        # Показываем статистику
        print("\n📊 Добавленные тестовые данные:")
        sku_totals = {}
        for movement in movements_to_add:
            sku = movement.blank_sku
            qty = abs(movement.qty)
            sku_totals[sku] = sku_totals.get(sku, 0) + qty
        
        for sku, total in sorted(sku_totals.items(), key=lambda x: x[1], reverse=True):
            print(f"  {sku}: -{total} шт")
            
        print(f"\n✅ Готово! Добавлено {len(movements_to_add)} тестовых движений")
        
    except Exception as e:
        logger.error(f"Failed to add test outbound data: {e}")
        raise


if __name__ == "__main__":
    try:
        add_test_outbound_data()
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
    except Exception as e:
        logger.error(f"Script failed: {e}")
        import sys
        sys.exit(1)