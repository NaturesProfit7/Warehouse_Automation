#!/usr/bin/env python3
"""Тест фильтрации адресников в StockService."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from datetime import datetime
from src.integrations.keycrm import KeyCRMOrderItem
from src.services.stock_service import StockService

def test_address_tag_filtering():
    """Тестирует фильтрацию товаров - только адресники обрабатываются."""
    
    print("🧪 ТЕСТ ФИЛЬТРАЦИИ АДРЕСНИКОВ")
    print("=" * 50)
    
    # Создаем тестовые товары
    test_items = [
        # Адресники - должны обрабатываться
        KeyCRMOrderItem(
            id=1,
            product_id=1,
            product_name="Адресник бублик",
            quantity=1,
            price=150.0,
            total=150.0,
            properties={"Розмір": "25 мм", "Колір": "золото"}
        ),
        KeyCRMOrderItem(
            id=2,
            product_id=2,
            product_name="Адресник фігурний",
            quantity=1,
            price=200.0,
            total=200.0,
            properties={"Форма": "серце", "Колір": "срібло"}
        ),
        KeyCRMOrderItem(
            id=3,
            product_id=3,
            product_name="жетон круглий",
            quantity=1,
            price=120.0,
            total=120.0,
            properties={"Розмір": "20 мм", "Колір": "золото"}
        ),
        
        # НЕ адресники - должны пропускаться
        KeyCRMOrderItem(
            id=4,
            product_id=4,
            product_name="Шнурок",
            quantity=2,
            price=25.0,
            total=50.0,
            properties={"Цвет": "Червоний"}
        ),
        KeyCRMOrderItem(
            id=5,
            product_id=5,
            product_name="Талісман дружби",
            quantity=1,
            price=80.0,
            total=80.0,
            properties={"Цвет": "Бежевий", "Вид": "DOG"}
        ),
        KeyCRMOrderItem(
            id=6,
            product_id=6,
            product_name="Пакети рулон",
            quantity=10,
            price=2.0,
            total=20.0,
            properties={}
        ),
    ]
    
    # Создаем экземпляр StockService (без настоящего sheets_client)
    stock_service = StockService(sheets_client=None)
    
    print("📋 Тестируем распознавание адресников:")
    
    address_tags = []
    non_address_tags = []
    
    for item in test_items:
        is_address_tag = stock_service._is_address_tag_product(item)
        
        if is_address_tag:
            address_tags.append(item)
            print(f"  ✅ '{item.product_name}' - АДРЕСНИК")
        else:
            non_address_tags.append(item)
            print(f"  ❌ '{item.product_name}' - НЕ адресник")
    
    print()
    print(f"📊 РЕЗУЛЬТАТЫ:")
    print(f"  • Адресники: {len(address_tags)} из {len(test_items)}")
    print(f"  • Пропущено: {len(non_address_tags)} из {len(test_items)}")
    
    # Проверяем правильность фильтрации
    expected_address_tags = {"Адресник бублик", "Адресник фігурний", "жетон круглий"}
    expected_non_address_tags = {"Шнурок", "Талісман дружби", "Пакети рулон"}
    
    actual_address_tag_names = {item.product_name for item in address_tags}
    actual_non_address_tag_names = {item.product_name for item in non_address_tags}
    
    print()
    if actual_address_tag_names == expected_address_tags:
        print("✅ Адресники правильно определены")
    else:
        print(f"❌ Ошибка в определении адресников:")
        print(f"   Ожидалось: {expected_address_tags}")
        print(f"   Получилось: {actual_address_tag_names}")
    
    if actual_non_address_tag_names == expected_non_address_tags:
        print("✅ Не-адресники правильно пропущены")
    else:
        print(f"❌ Ошибка в пропуске не-адресников:")
        print(f"   Ожидалось: {expected_non_address_tags}")
        print(f"   Получилось: {actual_non_address_tag_names}")
    
    print()
    print("🎯 ВЫВОД:")
    print(f"Система теперь будет обрабатывать только {len(address_tags)} адресника из {len(test_items)} товаров.")
    print(f"Остальные {len(non_address_tags)} товаров будут пропущены без создания движений.")
    
    return len(address_tags) == 3 and len(non_address_tags) == 3

if __name__ == "__main__":
    success = test_address_tag_filtering()
    if success:
        print("\n✅ ТЕСТ ПРОШЕЛ УСПЕШНО!")
    else:
        print("\n❌ ТЕСТ НЕУСПЕШЕН!")
        sys.exit(1)