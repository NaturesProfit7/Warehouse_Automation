#!/usr/bin/env python3
"""Скрипт очистки Google Sheets перед деплоем."""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.integrations.sheets import get_sheets_client
from src.utils.logger import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


def main():
    """Основная функция очистки."""
    logger.info("🧹 Starting Google Sheets cleanup before deploy...")
    
    try:
        # Получаем клиент
        sheets_client = get_sheets_client()
        
        # Выполняем очистку
        results = sheets_client.clear_data_sheets()
        
        # Подводим итоги
        success_count = sum(1 for v in results.values() if v)
        total_count = len(results)
        
        if success_count == total_count:
            logger.info("✅ Google Sheets cleanup completed successfully!")
            print("\n✅ Все листы очищены успешно:")
        else:
            logger.warning(f"⚠️ Partial cleanup: {success_count}/{total_count} sheets cleared")
            print(f"\n⚠️ Частичная очистка: {success_count}/{total_count} листов очищены:")
            
        for sheet_name, success in results.items():
            status = "✅" if success else "❌"
            print(f"  {status} {sheet_name}")
            
        if success_count < total_count:
            print("\nНекоторые листы не удалось очистить. Проверьте логи для деталей.")
            sys.exit(1)
        else:
            print("\nВсе данные готовы к чистому деплою!")
            
    except Exception as e:
        logger.error("Failed to cleanup Google Sheets", error=str(e))
        print(f"\n❌ Ошибка очистки Google Sheets: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()