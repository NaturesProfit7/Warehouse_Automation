#!/usr/bin/env python3
"""Manual test of webhook processing without KeyCRM API calls."""

import asyncio
import json
from datetime import datetime

async def test_webhook_processing():
    """Test webhook processing with simulated order data."""
    
    # Import after path setup
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
    
    from webhook.handlers import KeyCRMWebhookHandler
    from integrations.keycrm import KeyCRMOrder, KeyCRMOrderItem
    
    # Create handler
    handler = KeyCRMWebhookHandler()
    
    # Simulate webhook payload from KeyCRM
    webhook_payload = {
        "event": "order.change_order_status",
        "context": {
            "order_id": 4505,
            "status_id": 1,  # New order status
            "status": "new"
        },
        "timestamp": datetime.now().isoformat()
    }
    
    print("Testing webhook processing with simulated data...")
    print(f"Webhook payload: {json.dumps(webhook_payload, indent=2)}")
    
    # Simulate order data (since API is not working)
    simulated_order = KeyCRMOrder(
        id=4505,
        status="new",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        client_id=12345,
        grand_total=1500.0,
        items=[
            KeyCRMOrderItem(
                id=1,
                product_id=101,
                product_name="Заготовка круглая 10x20",
                quantity=5,
                price=150.0,
                total=750.0,
                properties={}
            ),
            KeyCRMOrderItem(
                id=2,
                product_id=102,
                product_name="Заготовка квадратная 15x15",
                quantity=3,
                price=250.0,
                total=750.0,
                properties={}
            )
        ],
        client_name="Иван Иванов",
        client_phone="+380501234567",
        delivery_address="Київ, вул. Хрещатик, 1",
        notes="Терміновий заказ"
    )
    
    print(f"\nSimulated order data:")
    print(f"Order ID: {simulated_order.id}")
    print(f"Status: {simulated_order.status}")
    print(f"Client: {simulated_order.client_name}")
    print(f"Total: {simulated_order.grand_total}")
    print(f"Items count: {len(simulated_order.items)}")
    
    for item in simulated_order.items:
        print(f"  - {item.product_name}: {item.quantity} шт x {item.price} = {item.total}")
    
    # Test the webhook handler logic manually
    print(f"\n{'='*60}")
    print("Testing webhook validation...")
    
    # Test event validation
    from webhook.auth import validate_keycrm_event
    
    should_process = validate_keycrm_event(webhook_payload)
    print(f"Should process event: {should_process}")
    
    if should_process:
        print(f"\n✅ Event validation passed!")
        print(f"Event: {webhook_payload['event']}")
        print(f"Order ID: {webhook_payload['context']['order_id']}")
        print(f"Status: {webhook_payload['context']['status']}")
        
        # For now, we'll skip the actual API call since it's not working
        print(f"\n⚠️  Skipping API call (KeyCRM API authentication issue)")
        print(f"In a working scenario, we would:")
        print(f"1. Fetch order {webhook_payload['context']['order_id']} from KeyCRM API")
        print(f"2. Process stock deduction for order items")
        print(f"3. Update Google Sheets with stock changes")
        print(f"4. Send Telegram notification")
        
        # Let's test the stock service part
        try:
            from services.stock_service import StockService
            stock_service = StockService()
            
            print(f"\n{'='*40}")
            print("Testing stock service operations...")
            
            # Test reading current stock
            print("Reading current stock from Google Sheets...")
            current_stock = await stock_service.get_current_stock()
            
            if current_stock:
                print(f"✅ Successfully read stock data: {len(current_stock)} items")
                
                # Show first few items
                for i, (item_name, data) in enumerate(list(current_stock.items())[:3]):
                    print(f"  {i+1}. {item_name}: {data.get('current_stock', 0)} шт")
                    
            else:
                print("❌ No stock data found")
                
        except Exception as e:
            print(f"❌ Stock service error: {e}")
        
    else:
        print(f"❌ Event validation failed - event will not be processed")

if __name__ == "__main__":
    asyncio.run(test_webhook_processing())