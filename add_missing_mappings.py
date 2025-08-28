#!/usr/bin/env python3
"""Скрипт для добавления недостающих маппингов KeyCRM продуктов."""

from datetime import datetime

from src.integrations.sheets import get_sheets_client
from src.core.models import ProductMapping
from src.utils.logger import get_logger

logger = get_logger(__name__)


def add_missing_mappings() -> None:
    """
    Добавляет недостающие маппинги для вариантов с 'x1'.
    """
    try:
        logger.info("Starting to add missing product mappings...")
        
        # Инициализируем клиент Google Sheets
        sheets_client = get_sheets_client()
        
        # Получаем существующие маппинги
        existing_mappings = sheets_client.get_product_mappings()
        
        print(f"\n📋 Текущие маппинги: {len(existing_mappings)}")
        
        # Создаем маппинги для вариантов с "x1"
        new_mappings = []
        
        # Основные варианты для добавления
        base_mappings = [
            ("Адресник", "Адресник x1"),
            ("Адресник бублик", "Адресник бублик x1"),  
            ("Адресник кістка", "Адресник кістка x1"),
            ("Адресник фігурний", "Адресник фігурний x1")
        ]
        
        for existing in existing_mappings:
            # Проверяем каждый существующий маппинг
            for base_name, x1_variant in base_mappings:
                if existing.product_name == base_name:
                    # Создаем аналогичный маппинг для x1 варианта
                    x1_mapping = ProductMapping(
                        product_name=x1_variant,
                        size_property=existing.size_property,
                        metal_color=existing.metal_color,
                        blank_sku=existing.blank_sku,  # Тот же SKU!
                        qty_per_unit=existing.qty_per_unit,
                        priority=existing.priority,
                        active=existing.active
                    )
                    
                    # Проверяем, не существует ли уже такой маппинг
                    already_exists = any(
                        m.product_name == x1_variant and
                        m.size_property == existing.size_property and
                        m.metal_color == existing.metal_color
                        for m in existing_mappings
                    )
                    
                    if not already_exists:
                        new_mappings.append(x1_mapping)
                        print(f"  ✅ {x1_variant} | {existing.size_property} | {existing.metal_color} → {existing.blank_sku}")
                    else:
                        print(f"  ⚠️  Маппинг {x1_variant} уже существует")
        
        if new_mappings:
            print(f"\n🔧 Добавляем {len(new_mappings)} новых маппингов...")
            
            # Добавляем новые маппинги напрямую в таблицу
            worksheet = sheets_client._get_worksheet("Mapping")
            
            # Подготавливаем данные для добавления
            rows_data = []
            for mapping in new_mappings:
                row_data = [
                    mapping.product_name,
                    mapping.size_property, 
                    mapping.metal_color,
                    mapping.blank_sku,
                    mapping.qty_per_unit,
                    mapping.active,
                    mapping.priority,
                    datetime.now().isoformat()
                ]
                rows_data.append(row_data)
            
            # Добавляем все строки одним запросом
            worksheet.append_rows(rows_data)
            
            print(f"\n✅ Успешно добавлено {len(new_mappings)} маппингов!")
            
            # Показываем добавленные маппинги
            print(f"\n📝 Добавленные маппинги:")
            for i, mapping in enumerate(new_mappings, 1):
                print(f"  {i:2d}. '{mapping.product_name}' | '{mapping.size_property}' | '{mapping.metal_color}' → {mapping.blank_sku}")
                
        else:
            print(f"\n✅ Все необходимые маппинги уже существуют!")
        
        # Показываем итоговую статистику
        total_mappings = len(existing_mappings) + len(new_mappings)
        print(f"\n📊 Итого маппингов: {total_mappings} (было: {len(existing_mappings)}, добавлено: {len(new_mappings)})")
        
    except Exception as e:
        logger.error(f"Failed to add missing mappings: {e}")
        raise


def show_mapping_summary() -> None:
    """Показывает сводку по маппингам."""
    try:
        logger.info("Showing mapping summary...")
        sheets_client = get_sheets_client()
        
        # Получаем все маппинги
        mappings = sheets_client.get_product_mappings()
        
        # Группируем по базовым типам
        groups = {}
        for mapping in mappings:
            base_name = mapping.product_name.replace(" x1", "")
            if base_name not in groups:
                groups[base_name] = []
            groups[base_name].append(mapping)
        
        print(f"\n📋 СВОДКА ПО МАППИНГАМ ({len(mappings)} всего):")
        
        for base_name in sorted(groups.keys()):
            group_mappings = groups[base_name]
            print(f"\n  🏷️  {base_name}: {len(group_mappings)} вариантов")
            
            for mapping in sorted(group_mappings, key=lambda x: (x.size_property, x.metal_color)):
                variant_marker = " x1" if " x1" in mapping.product_name else ""
                status = "✅" if mapping.active else "❌"
                print(f"    {status} {mapping.product_name} | {mapping.size_property} | {mapping.metal_color} → {mapping.blank_sku}")
        
    except Exception as e:
        logger.error(f"Failed to show mapping summary: {e}")


if __name__ == "__main__":
    try:
        print("🔧 Управление маппингами продуктов")
        print("1 - Показать текущее состояние маппингов")
        print("2 - Добавить недостающие маппинги для x1 вариантов")
        print("3 - Показать подробную сводку")
        
        choice = input("\nВыберите действие (1/2/3): ").strip()
        
        if choice == "1":
            sheets_client = get_sheets_client()
            mappings = sheets_client.get_product_mappings()
            print(f"\n📊 Текущее количество маппингов: {len(mappings)}")
            
        elif choice == "2":
            confirmation = input(f"\nДобавить недостающие x1 маппинги? (да/нет): ")
            if confirmation.lower() in ["да", "yes", "y"]:
                add_missing_mappings()
            else:
                print("❌ Операция отменена")
                
        elif choice == "3":
            show_mapping_summary()
            
        else:
            print("❌ Неверный выбор")
            
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
    except Exception as e:
        logger.error(f"Operation failed: {e}")
        import sys
        sys.exit(1)