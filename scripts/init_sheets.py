#!/usr/bin/env python3
"""Скрипт инициализации Google Sheets структуры."""

import sys
import os
from datetime import datetime

# Добавляем src в путь
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.integrations.sheets import GoogleSheetsClient
from src.utils.logger import configure_logging, get_logger
from src.config import settings

configure_logging()
logger = get_logger(__name__)


def init_config_sheet(client: GoogleSheetsClient) -> None:
    """Инициализация листа Config."""
    worksheet = client._get_worksheet("Config")
    
    headers = ["parameter", "value", "description", "updated_at", "updated_by"]
    
    config_data = [
        ["LEAD_TIME_DAYS", settings.LEAD_TIME_DAYS, "Срок поставки заготовок в днях", 
         datetime.now().isoformat(), "system"],
        ["SCRAP_PCT", settings.SCRAP_PCT, "Процент брака (5%)", 
         datetime.now().isoformat(), "system"],
        ["TARGET_COVER_DAYS", settings.TARGET_COVER_DAYS, "Дополнительная подушка безопасности", 
         datetime.now().isoformat(), "system"],
        ["MIN_STOCK_DEFAULT", settings.MIN_STOCK_DEFAULT, "Минимальный остаток по умолчанию", 
         datetime.now().isoformat(), "system"],
        ["PAR_STOCK_DEFAULT", settings.PAR_STOCK_DEFAULT, "Целевой остаток по умолчанию", 
         datetime.now().isoformat(), "system"],
    ]
    
    data_to_update = [headers] + config_data
    client._batch_update(worksheet, data_to_update)
    logger.info("Initialized Config sheet")


def init_unmapped_items_sheet(client: GoogleSheetsClient) -> None:
    """Инициализация листа Unmapped_Items."""
    worksheet = client._get_worksheet("Unmapped_Items")
    
    headers = [
        "datetime", "order_id", "line_id", "product_name", 
        "properties", "suggested_sku", "error_type", "resolution"
    ]
    
    client._batch_update(worksheet, [headers])
    logger.info("Initialized Unmapped_Items sheet")


def init_audit_log_sheet(client: GoogleSheetsClient) -> None:
    """Инициализация листа Audit_Log."""
    worksheet = client._get_worksheet("Audit_Log")
    
    headers = [
        "timestamp", "user_id", "user_name", "action", "entity",
        "entity_id", "old_value", "new_value", "source", "ip_address",
        "result", "error_message"
    ]
    
    client._batch_update(worksheet, [headers])
    logger.info("Initialized Audit_Log sheet")


def init_analytics_dashboard_sheet(client: GoogleSheetsClient) -> None:
    """Инициализация листа Analytics_Dashboard."""
    worksheet = client._get_worksheet("Analytics_Dashboard")
    
    headers = ["Метрика", "Значение", "Тренд", "Описание"]
    
    analytics_data = [
        ["total_skus", 20, "→", "Всего SKU"],
        ["skus_below_min", 0, "→", "Под минимумом"],
        ["total_value", "₴0", "→", "Стоимость остатков"],
        ["avg_turnover", 0, "→", "Оборачиваемость"],
        ["stockout_risk", "0%", "→", "Риск дефицита"],
    ]
    
    data_to_update = [headers] + analytics_data
    client._batch_update(worksheet, data_to_update)
    logger.info("Initialized Analytics_Dashboard sheet")


def init_current_stock_sheet(client: GoogleSheetsClient) -> None:
    """Инициализация листа Current_Stock."""
    worksheet = client._get_worksheet("Current_Stock")
    
    headers = [
        "blank_sku", "on_hand", "reserved", "available",
        "last_receipt_date", "last_order_date", "avg_daily_usage",
        "days_of_stock", "last_updated"
    ]
    
    # Создаем начальные остатки для всех 20 SKU
    stock_data = []
    sku_list = [
        "BLK-BONE-25-GLD", "BLK-BONE-25-SIL", "BLK-BONE-30-GLD", "BLK-BONE-30-SIL",
        "BLK-RING-25-GLD", "BLK-RING-25-SIL", "BLK-RING-30-GLD", "BLK-RING-30-SIL",
        "BLK-ROUND-20-GLD", "BLK-ROUND-20-SIL", "BLK-ROUND-25-GLD", "BLK-ROUND-25-SIL", 
        "BLK-ROUND-30-GLD", "BLK-ROUND-30-SIL",
        "BLK-HEART-25-GLD", "BLK-HEART-25-SIL",
        "BLK-CLOUD-25-GLD", "BLK-CLOUD-25-SIL",
        "BLK-FLOWER-25-GLD", "BLK-FLOWER-25-SIL"
    ]
    
    now = datetime.now().isoformat()
    for sku in sku_list:
        stock_data.append([
            sku, 200, 0, 200, "", "", 0.0, "", now
        ])
    
    data_to_update = [headers] + stock_data
    client._batch_update(worksheet, data_to_update)
    logger.info("Initialized Current_Stock sheet with 20 SKUs")


def main():
    """Главная функция инициализации."""
    try:
        logger.info("Starting Google Sheets initialization...")
        
        # Проверяем обязательные переменные окружения
        required_vars = ["GSHEETS_ID", "GOOGLE_CREDENTIALS_JSON"]
        missing_vars = [var for var in required_vars if not getattr(settings, var, None)]
        
        if missing_vars:
            logger.error(f"Missing required environment variables: {missing_vars}")
            sys.exit(1)
        
        # Создаем клиента
        client = GoogleSheetsClient()
        
        # Создаем все листы
        logger.info("Creating all worksheets...")
        client.create_all_worksheets()
        
        # Инициализируем каждый лист
        logger.info("Initializing Config sheet...")
        init_config_sheet(client)
        
        logger.info("Initializing Master_Blanks sheet...")
        client.initialize_master_blanks()
        
        logger.info("Initializing Mapping sheet...")
        client.initialize_mapping()
        
        logger.info("Initializing Current_Stock sheet...")
        init_current_stock_sheet(client)
        
        logger.info("Initializing other sheets...")
        init_unmapped_items_sheet(client)
        init_audit_log_sheet(client)
        init_analytics_dashboard_sheet(client)
        
        # Движения и отчеты будут создаваться динамически
        movements_sheet = client._get_worksheet("Movements")
        movements_headers = [
            "id", "datetime", "type", "source_type", "source_id",
            "blank_sku", "qty", "balance_after", "user", "note", "hash"
        ]
        client._batch_update(movements_sheet, [movements_headers])
        
        replenishment_sheet = client._get_worksheet("Replenishment_Report")
        replenishment_headers = [
            "blank_sku", "on_hand", "min_level", "reorder_point", "target_level",
            "need_order", "recommended_qty", "urgency", "estimated_stockout", "last_calculated"
        ]
        client._batch_update(replenishment_sheet, [replenishment_headers])
        
        logger.info("✅ Google Sheets initialization completed successfully!")
        logger.info(f"📊 Sheets ID: {settings.GSHEETS_ID}")
        logger.info("🔗 Access your sheets at: https://docs.google.com/spreadsheets/d/" + settings.GSHEETS_ID)
        
    except Exception as e:
        logger.error(f"❌ Initialization failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()