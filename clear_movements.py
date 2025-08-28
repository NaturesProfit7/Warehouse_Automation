#!/usr/bin/env python3
"""Скрипт для очистки всех движений (movements) из Google Sheets."""

from src.integrations.sheets import get_sheets_client
from src.utils.logger import get_logger

logger = get_logger(__name__)


def clear_movements() -> None:
    """Очищает все записи из таблицы Movements, оставляя только заголовки."""
    try:
        logger.info("Starting to clear all movements...")
        
        # Инициализируем клиент Google Sheets
        sheets_client = get_sheets_client()
        
        # Получаем рабочий лист Movements
        worksheet = sheets_client._get_worksheet("Movements")
        
        # Получаем количество строк с данными
        all_records = worksheet.get_all_records()
        total_records = len(all_records)
        
        logger.info(f"Found {total_records} movement records to delete")
        
        if total_records > 0:
            # Очищаем все строки кроме заголовка (начиная со второй строки)
            if worksheet.row_count > 1:
                # Удаляем строки с данными (оставляем заголовок)
                worksheet.delete_rows(2, worksheet.row_count)
                logger.info(f"✅ Deleted {total_records} movement records")
            else:
                logger.info("No data rows to delete")
        else:
            logger.info("Movements table is already empty")
        
        print(f"\n🧹 Очистка movements завершена!")
        print(f"❌ Удалено записей: {total_records}")
        print(f"📋 Заголовки сохранены")
        
    except Exception as e:
        logger.error(f"Failed to clear movements: {e}")
        raise


def show_movements_count() -> None:
    """Показывает количество движений в таблице."""
    try:
        logger.info("Checking movements count...")
        sheets_client = get_sheets_client()
        
        # Получаем рабочий лист Movements
        worksheet = sheets_client._get_worksheet("Movements")
        all_records = worksheet.get_all_records()
        
        print(f"\n📊 Текущее состояние таблицы Movements:")
        print(f"   Всего записей: {len(all_records)}")
        
        if all_records:
            # Показываем последние 5 записей
            print(f"\n   Последние записи:")
            for i, record in enumerate(all_records[-5:], 1):
                sku = record.get('blank_sku', 'N/A')
                qty = record.get('qty', 'N/A') 
                date = record.get('datetime', 'N/A')
                print(f"     {i}. {sku}: {qty} ({date})")
        else:
            print(f"   📭 Таблица пуста")
            
    except Exception as e:
        logger.error(f"Failed to show movements count: {e}")


if __name__ == "__main__":
    try:
        print("🧹 Управление таблицей Movements")
        print("1 - Показать текущее количество записей")
        print("2 - ОЧИСТИТЬ ВСЕ движения")
        
        choice = input("\nВыберите действие (1/2): ").strip()
        
        if choice == "1":
            show_movements_count()
        elif choice == "2":
            show_movements_count()  # Сначала показываем что есть
            
            confirmation = input(f"\n⚠️  УДАЛИТЬ ВСЕ движения? Это действие нельзя отменить! (да/нет): ")
            
            if confirmation.lower() in ["да", "yes", "y"]:
                clear_movements()
            else:
                print("❌ Операция отменена")
        else:
            print("❌ Неверный выбор")
            
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
    except Exception as e:
        logger.error(f"Operation failed: {e}")
        import sys
        sys.exit(1)