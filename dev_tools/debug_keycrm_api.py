#!/usr/bin/env python3
"""Debug script for KeyCRM API calls."""

import asyncio
import httpx
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def test_keycrm_api():
    """Test KeyCRM API with different configurations."""
    
    api_token = os.getenv("KEYCRM_API_TOKEN")
    print(f"API Token: {api_token[:10]}... (length: {len(api_token)})")
    
    # Test different base URLs and authentication methods
    test_configs = [
        {
            "name": "api.keycrm.app with Bearer",
            "base_url": "https://api.keycrm.app",
            "headers": {
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json"
            }
        },
        {
            "name": "api.keycrm.app with X-Token",
            "base_url": "https://api.keycrm.app",
            "headers": {
                "X-Token": api_token,
                "Content-Type": "application/json"
            }
        },
        {
            "name": "api.keycrm.app/v1 with Bearer",
            "base_url": "https://api.keycrm.app/v1",
            "headers": {
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json"
            }
        },
        {
            "name": "openapi.keycrm.app/v1 with Bearer",
            "base_url": "https://openapi.keycrm.app/v1",
            "headers": {
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json"
            }
        }
    ]
    
    order_id = 4505  # Last created order
    
    for config in test_configs:
        print(f"\n{'='*60}")
        print(f"Testing: {config['name']}")
        print(f"URL: {config['base_url']}/orders/{order_id}")
        print(f"{'='*60}")
        
        try:
            async with httpx.AsyncClient(
                base_url=config['base_url'],
                timeout=10.0,
                headers=config['headers']
            ) as client:
                
                # Test orders endpoint
                response = await client.get(f"/orders/{order_id}")
                
                print(f"Status Code: {response.status_code}")
                print(f"Content-Type: {response.headers.get('Content-Type', 'Not specified')}")
                print(f"Response Size: {len(response.content)} bytes")
                
                # Show response preview
                text = response.text[:300]
                print(f"Response Preview: {text}...")
                
                if response.status_code == 200:
                    content_type = response.headers.get("Content-Type", "")
                    if "application/json" in content_type:
                        try:
                            data = response.json()
                            print(f"✅ JSON Response: {list(data.keys()) if isinstance(data, dict) else type(data)}")
                        except Exception as e:
                            print(f"❌ JSON Parse Error: {e}")
                    else:
                        print(f"❌ Non-JSON response: {content_type}")
                else:
                    print(f"❌ HTTP Error: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Request Error: {e}")
    
    # Also test general endpoints
    print(f"\n{'='*60}")
    print("Testing general endpoints")
    print(f"{'='*60}")
    
    for config in test_configs[:2]:  # Test first two configs only
        print(f"\nTesting {config['name']} - /orders endpoint")
        
        try:
            async with httpx.AsyncClient(
                base_url=config['base_url'],
                timeout=10.0,
                headers=config['headers']
            ) as client:
                
                response = await client.get("/orders", params={"limit": 1})
                print(f"GET /orders: {response.status_code} - {response.headers.get('Content-Type')}")
                
                if response.status_code == 200 and "application/json" in response.headers.get('Content-Type', ''):
                    try:
                        data = response.json()
                        print(f"✅ Orders list: {list(data.keys()) if isinstance(data, dict) else 'Success'}")
                    except:
                        print("❌ JSON parse error")
                
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_keycrm_api())