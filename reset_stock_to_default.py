#!/usr/bin/env python3
"""Скрипт для обновления остатков всех SKU на значение по умолчанию."""

from datetime import date, datetime
from typing import List

from src.integrations.sheets import get_sheets_client
from src.core.models import CurrentStock
from src.utils.logger import get_logger

logger = get_logger(__name__)


def reset_stock_to_default(default_quantity: int = 200) -> None:
    """
    Обновляет остатки всех SKU на указанное значение.
    
    Args:
        default_quantity: Количество по умолчанию для всех SKU
    """
    try:
        logger.info(f"Resetting all stock to default quantity: {default_quantity}")
        
        # Инициализируем клиент Google Sheets
        sheets_client = get_sheets_client()
        
        # Получаем все мастер-заготовки для списка SKU
        master_blanks = sheets_client.get_master_blanks()
        logger.info(f"Found {len(master_blanks)} master blanks")
        
        # Создаем остатки со значениями по умолчанию
        stocks_to_update = []
        
        for blank in master_blanks:
            if blank.active:  # Только активные SKU
                stock = CurrentStock(
                    blank_sku=blank.blank_sku,
                    on_hand=default_quantity,
                    reserved=0,
                    available=default_quantity,
                    last_receipt_date=None,
                    last_order_date=None,
                    avg_daily_usage=0.0,
                    days_of_stock=None,
                    last_updated=datetime.now()
                )
                stocks_to_update.append(stock)
        
        logger.info(f"Prepared {len(stocks_to_update)} stock records for update")
        
        if stocks_to_update:
            # Обновляем остатки в Google Sheets
            sheets_client.update_current_stock(stocks_to_update)
            logger.info(f"✅ Updated stock for {len(stocks_to_update)} SKUs")
            
            # Показываем обновленные SKU
            print("\n📦 Обновленные остатки:")
            for stock in stocks_to_update:
                print(f"  {stock.blank_sku}: {stock.on_hand} шт")
            
        print(f"\n✅ Обновление завершено!")
        print(f"📊 Всего SKU обновлено: {len(stocks_to_update)}")
        print(f"💯 Остаток по умолчанию: {default_quantity} шт")
        
    except Exception as e:
        logger.error(f"Failed to reset stock: {e}")
        raise


def show_current_stock() -> None:
    """Показывает текущие остатки всех SKU."""
    try:
        logger.info("Retrieving current stock...")
        sheets_client = get_sheets_client()
        
        # Получаем текущие остатки
        current_stocks = sheets_client.get_current_stock()
        
        if current_stocks:
            print("\n📊 Текущие остатки:")
            for stock in sorted(current_stocks, key=lambda x: x.blank_sku):
                print(f"  {stock.blank_sku}: {stock.on_hand} шт (доступно: {stock.available})")
        else:
            print("\n📭 Остатки не найдены")
            
    except Exception as e:
        logger.error(f"Failed to show current stock: {e}")


if __name__ == "__main__":
    try:
        print("🔧 Управление остатками склада")
        print("1 - Показать текущие остатки")
        print("2 - Обновить все остатки на значение по умолчанию")
        
        choice = input("\nВыберите действие (1/2): ").strip()
        
        if choice == "1":
            show_current_stock()
        elif choice == "2":
            default_qty = int(input("Введите количество по умолчанию (200): ") or "200")
            confirmation = input(f"Обновить ВСЕ остатки на {default_qty} шт? (да/нет): ")
            
            if confirmation.lower() in ["да", "yes", "y"]:
                reset_stock_to_default(default_qty)
            else:
                print("Операция отменена")
        else:
            print("Неверный выбор")
            
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
    except Exception as e:
        logger.error(f"Operation failed: {e}")
        import sys
        sys.exit(1)