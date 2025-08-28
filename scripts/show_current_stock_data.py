#!/usr/bin/env python3
"""Скрипт показывает данные для заполнения Current_Stock."""

from datetime import datetime

def show_current_stock_data():
    """Показать данные для заполнения Current_Stock по маппингам."""
    
    # Список всех SKU из маппингов (как в init_sheets.py)
    sku_list = [
        "BLK-BONE-25-GLD", "BLK-BONE-25-SIL", "BLK-BONE-30-GLD", "BLK-BONE-30-SIL",
        "BLK-RING-25-GLD", "BLK-RING-25-SIL", "BLK-RING-30-GLD", "BLK-RING-30-SIL",
        "BLK-ROUND-20-GLD", "BLK-ROUND-20-SIL", "BLK-ROUND-25-GLD", "BLK-ROUND-25-SIL", 
        "BLK-ROUND-30-GLD", "BLK-ROUND-30-SIL",
        "BLK-HEART-25-GLD", "BLK-HEART-25-SIL",
        "BLK-CLOUD-25-GLD", "BLK-CLOUD-25-SIL",
        "BLK-FLOWER-25-GLD", "BLK-FLOWER-25-SIL"
    ]
    
    # Заголовки для Current_Stock
    headers = [
        "blank_sku", "on_hand", "reserved", "available",
        "last_receipt_date", "last_order_date", "avg_daily_usage",
        "days_of_stock", "last_updated"
    ]
    
    print("🔗 Данные для заполнения листа Current_Stock в Google Таблице")
    print("="*80)
    print()
    
    print("📋 ЗАГОЛОВКИ (строка 1):")
    print("\t".join(headers))
    print()
    
    print("📊 ДАННЫЕ (строки 2-21):")
    now = datetime.now().isoformat()
    
    for i, sku in enumerate(sku_list, 2):
        row_data = [
            sku,            # blank_sku
            "200",          # on_hand (начальный остаток)
            "0",            # reserved
            "200",          # available
            "",             # last_receipt_date (пусто)
            "",             # last_order_date (пусто)
            "0.0",          # avg_daily_usage
            "",             # days_of_stock (пусто)
            now             # last_updated
        ]
        print(f"Строка {i}:\t" + "\t".join(row_data))
    
    print()
    print("📝 ИНСТРУКЦИЯ ПО ЗАПОЛНЕНИЮ:")
    print("1. Откройте Google Таблицу")
    print("2. Перейдите на лист 'Current_Stock'")
    print("3. Если лист пустой, скопируйте заголовки в строку 1")
    print("4. Скопируйте данные в строки 2-21")
    print("5. Все SKU получат начальный остаток 200 штук")
    print()
    
    print("✅ ГОТОВО! Лист Current_Stock будет содержать все 20 SKU.")
    print(f"📅 Время обновления: {now}")

if __name__ == "__main__":
    show_current_stock_data()