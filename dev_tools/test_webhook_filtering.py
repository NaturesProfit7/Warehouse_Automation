#!/usr/bin/env python3
"""Тест фильтрации товаров через webhook."""

import asyncio
import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from datetime import datetime
from src.webhook.handlers import KeyCRMWebhookHandler
from src.integrations.keycrm import KeyCRMClient

async def test_webhook_filtering():
    """Тестирует обработку webhook с фильтрацией товаров."""
    
    print("🧪 ТЕСТ WEBHOOK ФИЛЬТРАЦИИ")
    print("=" * 50)
    
    # Имитация webhook payload от KeyCRM для смешанного заказа
    webhook_payload = {
        "event": "order.change_order_status",
        "context": {
            "id": 9999,  # Тестовый ID
            "status": "new",
            "status_id": 1,  # Новый заказ
            "created_at": datetime.now().isoformat() + "Z",
            "updated_at": datetime.now().isoformat() + "Z",
            "grand_total": 400.0,
            "client_id": 123,
            "client_name": "Тестовый клиент",
            "products": [
                # Адресники - должны обрабатываться
                {
                    "id": 1,
                    "name": "Адресник бублик",
                    "quantity": 1,
                    "price": 150.0,
                    "properties": [
                        {"name": "Розмір", "value": "25 мм"},
                        {"name": "Колір", "value": "золото"}
                    ]
                },
                {
                    "id": 2,
                    "name": "жетон круглий", 
                    "quantity": 1,
                    "price": 120.0,
                    "properties": [
                        {"name": "Розмір", "value": "20 мм"},
                        {"name": "Колір", "value": "срібло"}
                    ]
                },
                # Не-адресники - должны пропускаться
                {
                    "id": 3,
                    "name": "Шнурок",
                    "quantity": 2,
                    "price": 25.0,
                    "properties": [
                        {"name": "Цвет", "value": "Червоний"}
                    ]
                },
                {
                    "id": 4,
                    "name": "Талісман дружби",
                    "quantity": 1,
                    "price": 80.0,
                    "properties": [
                        {"name": "Цвет", "value": "Бежевий"},
                        {"name": "Вид", "value": "DOG"}
                    ]
                },
                {
                    "id": 5,
                    "name": "Пакети рулон",
                    "quantity": 10,
                    "price": 2.5,
                    "properties": []
                }
            ]
        }
    }
    
    print("📦 Тестовый заказ содержит:")
    print("  АДРЕСНИКИ:")
    print("    • Адресник бублик (золото, 25 мм)")
    print("    • жетон круглий (срібло, 20 мм)")
    print("  НЕ-АДРЕСНИКИ:")
    print("    • Шнурок (красный) x2")
    print("    • Талісман дружби (бежевый DOG)")
    print("    • Пакети рулон x10")
    print()
    
    print("🔄 Обработка webhook...")
    
    try:
        # Создаем обработчик и обрабатываем webhook
        handler = KeyCRMWebhookHandler()
        result = await handler.handle_keycrm_webhook(webhook_payload, "test-request-123")
        print("✅ Webhook успешно обработан")
        
        if result:
            print(f"📊 Результат обработки: {result}")
        else:
            print("ℹ️  Обработка завершена без движений")
            
    except Exception as e:
        print(f"❌ Ошибка обработки: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("🎯 Ожидаемое поведение:")
    print("  • Адресники → создать движения по остаткам")
    print("  • Остальные товары → пропустить без обработки")
    print("  • В логах должны быть записи о пропущенных товарах")

if __name__ == "__main__":
    asyncio.run(test_webhook_filtering())