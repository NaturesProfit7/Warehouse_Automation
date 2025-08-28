#!/usr/bin/env python3
"""Проверка маппингов в Google Sheets."""

import os
import sys
import json
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials

def check_mappings():
    print('🔍 ПРОВЕРКА МАППИНГОВ В GOOGLE SHEETS')
    print('='*50)
    
    load_dotenv()
    
    # Настройка Google Sheets
    credentials_json = json.loads(os.getenv('GOOGLE_CREDENTIALS_JSON'))
    sheets_id = os.getenv('GSHEETS_ID')
    
    credentials = Credentials.from_service_account_info(
        credentials_json,
        scopes=['https://www.googleapis.com/auth/spreadsheets']
    )
    
    client = gspread.authorize(credentials)
    spreadsheet = client.open_by_key(sheets_id)
    
    try:
        worksheet = spreadsheet.worksheet("Mapping")
        records = worksheet.get_all_records()
        
        print(f'📋 Всего маппингов: {len(records)}')
        print()
        
        # Поиск маппингов для адресников
        addressnik_mappings = [
            r for r in records 
            if 'адресник' in r.get('product_name', '').lower() or 
               'ring' in r.get('sku', '').lower() or
               'BLK' in r.get('sku', '').upper()
        ]
        
        if addressnik_mappings:
            print('🎯 МАППИНГИ ДЛЯ АДРЕСНИКОВ:')
            for i, mapping in enumerate(addressnik_mappings, 1):
                print(f'  {i}. "{mapping.get("product_name", "")}"')
                print(f'     • SKU: {mapping.get("sku", "")}')
                print(f'     • Size: {mapping.get("size", "")}')
                print(f'     • Metal Color: {mapping.get("metal_color", "")}')
                print(f'     • Design: {mapping.get("design", "")}')
                print()
        else:
            print('❌ НЕТ МАППИНГОВ ДЛЯ АДРЕСНИКОВ!')
            
        # Показываем структуру первых маппингов
        print('📋 СТРУКТУРА МАППИНГОВ (первые 3):')
        for i, mapping in enumerate(records[:3], 1):
            print(f'  {i}. "{mapping.get("product_name", "")}"')
            print(f'     • SKU: {mapping.get("sku", "")}')
            print(f'     • Size: {mapping.get("size", "")}')
            print(f'     • Metal Color: {mapping.get("metal_color", "")}')
            print(f'     • Design: {mapping.get("design", "")}')
            print(f'     • All keys: {list(mapping.keys())}')
            print()
            
        # Специально ищем товар "Адресник бублик"
        exact_matches = [
            r for r in records 
            if r.get('product_name', '').strip().lower() == 'адресник бублик'
        ]
        
        if exact_matches:
            print('✅ НАЙДЕН ТОЧНЫЙ МАППИНГ ДЛЯ "Адресник бублик":')
            for mapping in exact_matches:
                print(f'   • SKU: {mapping.get("sku", "")}')
                print(f'   • Properties: size={mapping.get("size", "")}, metal_color={mapping.get("metal_color", "")}, design={mapping.get("design", "")}')
        else:
            print('❌ НЕТ ТОЧНОГО МАППИНГА ДЛЯ "Адресник бублик"')
            
        return records
        
    except Exception as e:
        print(f'❌ Ошибка доступа к таблице Mapping: {e}')
        return []

if __name__ == "__main__":
    check_mappings()