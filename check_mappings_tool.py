#!/usr/bin/env python3
"""Инструмент для проверки и анализа маппингов товаров."""

import os
import sys
import json
import asyncio
from datetime import date, timedelta
from typing import Dict, List, Set
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials
import httpx

def setup_sheets():
    """Настройка Google Sheets клиента."""
    load_dotenv()
    credentials_json = json.loads(os.getenv('GOOGLE_CREDENTIALS_JSON'))
    sheets_id = os.getenv('GSHEETS_ID')
    
    credentials = Credentials.from_service_account_info(
        credentials_json,
        scopes=['https://www.googleapis.com/auth/spreadsheets']
    )
    
    client = gspread.authorize(credentials)
    spreadsheet = client.open_by_key(sheets_id)
    return spreadsheet

def get_all_mappings(spreadsheet):
    """Получение всех маппингов из Google Sheets."""
    try:
        worksheet = spreadsheet.worksheet("Mapping")
        mappings = worksheet.get_all_records()
        
        # Фильтруем активные маппинги
        active_mappings = [m for m in mappings if m.get('active', True)]
        return active_mappings
    except Exception as e:
        print(f"❌ Ошибка получения маппингов: {e}")
        return []

async def get_recent_keycrm_products():
    """Получение товаров из последних заказов KeyCRM."""
    load_dotenv()
    token = os.getenv('KEYCRM_API_TOKEN')
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json'
    }
    
    # Получаем заказы за последние 30 дней
    start_date = date.today() - timedelta(days=30)
    end_date = date.today()
    
    params = {
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        'limit': 100
    }
    
    products = []
    
    try:
        async with httpx.AsyncClient(
            base_url="https://openapi.keycrm.app/v1", 
            timeout=30.0
        ) as client:
            # Получаем список заказов
            response = await client.get("/order", headers=headers, params=params)
            response.raise_for_status()
            
            orders = response.json().get('data', [])
            print(f"📋 Найдено заказов: {len(orders)}")
            
            # Для каждого заказа получаем детали с товарами
            for order in orders[:20]:  # Ограничиваем для скорости
                try:
                    detail_response = await client.get(
                        f"/order/{order['id']}", 
                        headers=headers, 
                        params={'include': 'products'}
                    )
                    detail_response.raise_for_status()
                    order_detail = detail_response.json()
                    
                    for product in order_detail.get('products', []):
                        product_info = {
                            'order_id': order['id'],
                            'product_name': product.get('name', ''),
                            'properties': {}
                        }
                        
                        # Обрабатываем properties
                        props = product.get('properties', [])
                        if isinstance(props, list):
                            for prop in props:
                                if isinstance(prop, dict):
                                    product_info['properties'][prop.get('name', '')] = prop.get('value', '')
                        
                        products.append(product_info)
                        
                except Exception as e:
                    print(f"⚠️  Ошибка получения деталей заказа {order['id']}: {e}")
                    continue
    
    except Exception as e:
        print(f"❌ Ошибка получения заказов: {e}")
    
    return products

def analyze_mappings(mappings, keycrm_products):
    """Анализ покрытия маппингов."""
    print("\\n🔍 АНАЛИЗ МАППИНГОВ")
    print("=" * 60)
    
    # Группируем маппинги по названию товара
    mapping_by_product = {}
    for mapping in mappings:
        product_name = mapping.get('product_name', '').strip().lower()
        if product_name:
            if product_name not in mapping_by_product:
                mapping_by_product[product_name] = []
            mapping_by_product[product_name].append(mapping)
    
    print(f"📋 Всего активных маппингов: {len(mappings)}")
    print(f"📦 Уникальных товаров в маппинге: {len(mapping_by_product)}")
    print()
    
    # Анализируем покрытие товаров из KeyCRM
    covered_products = set()
    uncovered_products = []
    
    for product in keycrm_products:
        product_name = product['product_name'].strip().lower()
        color = product['properties'].get('Колір', '').strip()
        size = product['properties'].get('Розмір', '').strip()
        
        # Ищем подходящий маппинг
        found_mapping = False
        
        if product_name in mapping_by_product:
            for mapping in mapping_by_product[product_name]:
                # Проверяем совпадение цвета (если указан в маппинге)
                mapping_color = mapping.get('metal_color', '').strip()
                color_match = (not mapping_color or mapping_color.lower() == color.lower())
                
                # Проверяем совпадение размера (если указан в маппинге)  
                mapping_size = mapping.get('size_property', '').strip()
                size_match = (not mapping_size or mapping_size.lower() == size.lower())
                
                if color_match and size_match:
                    found_mapping = True
                    covered_products.add(f"{product_name} ({color}, {size})")
                    break
        
        if not found_mapping:
            uncovered_products.append({
                'name': product['product_name'],
                'properties': product['properties'],
                'order_id': product['order_id']
            })
    
    print(f"✅ Товаров с маппингом: {len(covered_products)}")
    print(f"❌ Товаров без маппинга: {len(uncovered_products)}")
    
    if uncovered_products:
        print("\\n⚠️  ТОВАРЫ БЕЗ МАППИНГА:")
        unique_uncovered = {}
        for product in uncovered_products:
            key = f"{product['name']}_{json.dumps(product['properties'], sort_keys=True)}"
            if key not in unique_uncovered:
                unique_uncovered[key] = product
        
        for i, product in enumerate(unique_uncovered.values(), 1):
            print(f"  {i}. {product['name']}")
            if product['properties']:
                for prop_name, prop_value in product['properties'].items():
                    print(f"     • {prop_name}: {prop_value}")
            print(f"     📦 Последний заказ: {product['order_id']}")
            print()

def show_mapping_structure(mappings):
    """Показать структуру маппингов."""
    print("\\n📋 СТРУКТУРА МАППИНГОВ")
    print("=" * 60)
    
    # Группируем по товарам
    by_product = {}
    for mapping in mappings:
        product_name = mapping.get('product_name', '').strip()
        if product_name:
            if product_name not in by_product:
                by_product[product_name] = []
            by_product[product_name].append(mapping)
    
    for product_name, product_mappings in by_product.items():
        print(f"📦 {product_name} ({len(product_mappings)} маппингов)")
        
        for i, mapping in enumerate(product_mappings, 1):
            sku = mapping.get('blank_sku', 'НЕТ SKU').strip()
            metal_color = mapping.get('metal_color', '').strip() or 'любой'
            size = mapping.get('size_property', '').strip() or 'любой'
            priority = mapping.get('priority', 0)
            qty_per_unit = mapping.get('qty_per_unit', 1)
            
            print(f"  {i}. SKU: {sku}")
            print(f"     • Цвет: {metal_color}")
            print(f"     • Размер: {size}")
            print(f"     • Приоритет: {priority}")
            print(f"     • Расход на 1шт: {qty_per_unit}")
            
        print()

def check_mapping_completeness(mappings):
    """Проверка полноты маппингов."""
    print("\\n🔍 ПРОВЕРКА ПОЛНОТЫ МАППИНГОВ")
    print("=" * 60)
    
    issues = []
    
    for mapping in mappings:
        product_name = mapping.get('product_name', '').strip()
        blank_sku = mapping.get('blank_sku', '').strip()
        
        # Проверки
        if not product_name:
            issues.append("❌ Пустое название товара")
        
        if not blank_sku:
            issues.append(f"❌ Нет SKU для товара: {product_name}")
        
        qty_per_unit = mapping.get('qty_per_unit')
        if not qty_per_unit or qty_per_unit <= 0:
            issues.append(f"⚠️  Некорректное количество на единицу для {product_name}: {qty_per_unit}")
    
    if issues:
        print("🔧 НАЙДЕННЫЕ ПРОБЛЕМЫ:")
        for issue in issues:
            print(f"  {issue}")
    else:
        print("✅ Все маппинги корректны!")

async def main():
    """Основная функция."""
    print("🔍 АНАЛИЗАТОР МАППИНГОВ ТОВАРОВ")
    print("=" * 60)
    
    # Получаем данные
    print("1️⃣ Получение маппингов из Google Sheets...")
    spreadsheet = setup_sheets()
    mappings = get_all_mappings(spreadsheet)
    
    print("2️⃣ Получение товаров из последних заказов KeyCRM...")
    keycrm_products = await get_recent_keycrm_products()
    
    # Анализы
    analyze_mappings(mappings, keycrm_products)
    show_mapping_structure(mappings)
    check_mapping_completeness(mappings)
    
    print("\\n🎯 РЕКОМЕНДАЦИИ:")
    print("1. Создайте маппинги для товаров без покрытия")
    print("2. Заполните пустые SKU в существующих маппингах")
    print("3. Проверьте корректность qty_per_unit")
    print("4. Установите приоритеты для конфликтующих маппингов")
    
    print("\\n✅ Анализ завершен!")

if __name__ == "__main__":
    asyncio.run(main())