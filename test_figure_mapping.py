#!/usr/bin/env python3
"""Тест маппинга фигурного адресника."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.integrations.keycrm import KeyCRMOrderItem
from src.services.stock_service import StockService

def test_figure_mapping():
    """Тестирует маппинг фигурного адресника с полем Форма."""
    
    print("🧪 ТЕСТ МАППИНГА ФИГУРНОГО АДРЕСНИКА")
    print("=" * 50)
    
    # Тестовый товар как из KeyCRM
    test_item = KeyCRMOrderItem(
        id=1,
        product_id=1,
        product_name="Адресник фігурний",
        quantity=1,
        price=550.0,
        total=550.0,
        properties={
            "Форма": "квітка",      # KeyCRM присылает "Форма" для фигурных
            "Колір": "золото",      # "Колір" как обычно
            "Шнурок": "червоний"    # Дополнительное свойство
        }
    )
    
    print("📦 Тестовый товар:")
    print(f"  • Название: {test_item.product_name}")
    print(f"  • Свойства: {test_item.properties}")
    print()
    
    # Создаем StockService 
    stock_service = StockService(sheets_client=None)
    
    # Проверяем распознавание как адресника
    is_address_tag = stock_service._is_address_tag_product(test_item)
    print(f"🎯 Распознан как адресник: {is_address_tag}")
    
    if is_address_tag:
        try:
            # Пытаемся найти маппинг
            mapping = stock_service._find_mapping_for_item(test_item)
            
            if mapping:
                print("✅ МАППИНГ НАЙДЕН!")
                print(f"  • SKU: {mapping.blank_sku}")
                print(f"  • Название в маппинге: {mapping.product_name}")
                print(f"  • Размер/форма в маппинге: {mapping.size_property}")
                print(f"  • Цвет в маппинге: {mapping.metal_color}")
                print(f"  • Приоритет: {mapping.priority}")
            else:
                print("❌ МАППИНГ НЕ НАЙДЕН")
                print("Проверьте:")
                print("1. Есть ли в Google Sheets маппинг с такими параметрами")
                print("2. Точно ли совпадают названия")
                
        except Exception as e:
            print(f"❌ Ошибка поиска маппинга: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("❌ Товар не распознан как адресник")
    
    print()
    print("🔍 Ожидаемый маппинг в Google Sheets:")
    print("  • product_name: 'Адресник фігурний'")
    print("  • size_property: 'квітка'")
    print("  • metal_color: 'золото'") 
    print("  • blank_sku: 'BLK-FLOWER-25-GLD'")

if __name__ == "__main__":
    test_figure_mapping()