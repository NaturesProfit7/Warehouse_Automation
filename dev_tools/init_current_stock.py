#!/usr/bin/env python3
"""Скрипт для инициализации таблицы Current_Stock из Master_Blanks."""

import asyncio
import sys
from datetime import datetime

from src.integrations.sheets import get_sheets_client
from src.core.models import CurrentStock
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def init_current_stock_from_master():
    """Инициализация Current_Stock из Master_Blanks с нулевыми остатками."""
    
    try:
        logger.info("Starting Current_Stock initialization...")
        
        # Получаем клиент Sheets
        sheets_client = get_sheets_client()
        
        # Получаем все Master_Blanks
        master_blanks = sheets_client.get_master_blanks()
        logger.info(f"Retrieved {len(master_blanks)} master blanks")
        
        # Создаем Current_Stock записи с нулевыми остатками
        current_stocks = []
        for blank in master_blanks:
            if blank.active:  # Только активные SKU
                stock = CurrentStock(
                    blank_sku=blank.blank_sku,
                    on_hand=blank.opening_stock or 0,  # Используем opening_stock или 0
                    reserved=0,
                    available=blank.opening_stock or 0,
                    last_receipt_date=None,
                    last_order_date=None,
                    avg_daily_usage=0.0,
                    days_of_stock=None,
                    last_updated=datetime.now()
                )
                current_stocks.append(stock)
                logger.info(f"Prepared stock record: {blank.blank_sku} = {stock.on_hand}")
        
        # Очищаем Current_Stock лист и записываем новые данные
        logger.warning("⚠️ ВНИМАНИЕ: Сейчас будет полностью перезаписан лист Current_Stock!")
        logger.info("Автоматическое выполнение - продолжаем...")
            
        # Полностью перезаписываем таблицу
        worksheet = sheets_client._get_worksheet("Current_Stock")
        
        # Заголовки
        headers = [
            "blank_sku", "on_hand", "reserved", "available",
            "last_receipt_date", "last_order_date", "avg_daily_usage",
            "days_of_stock", "last_updated"
        ]
        
        # Подготавливаем данные
        data_to_write = [headers]
        for stock in current_stocks:
            row = [
                stock.blank_sku,
                stock.on_hand,
                stock.reserved,
                stock.available,
                stock.last_receipt_date.isoformat() if stock.last_receipt_date else "",
                stock.last_order_date.isoformat() if stock.last_order_date else "",
                stock.avg_daily_usage,
                stock.days_of_stock or "",
                stock.last_updated.isoformat()
            ]
            data_to_write.append(row)
        
        # Очищаем лист
        worksheet.clear()
        logger.info("Cleared Current_Stock worksheet")
        
        # Записываем новые данные
        rows = len(data_to_write)
        cols = len(headers)
        range_name = f"A1:{chr(65 + cols - 1)}{rows}"
        
        worksheet.batch_update([{
            'range': range_name,
            'values': data_to_write
        }])
        
        logger.info(f"✅ Successfully initialized Current_Stock with {len(current_stocks)} records")
        
        # Показываем результат
        print("\n📊 Инициализированные записи:")
        for stock in current_stocks:
            print(f"  {stock.blank_sku}: {stock.on_hand} шт")
            
        print(f"\n✅ Готово! Инициализировано {len(current_stocks)} SKU в Current_Stock")
        
    except Exception as e:
        logger.error(f"Failed to initialize Current_Stock: {e}")
        raise


if __name__ == "__main__":
    try:
        asyncio.run(init_current_stock_from_master())
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
    except Exception as e:
        logger.error(f"Script failed: {e}")
        sys.exit(1)