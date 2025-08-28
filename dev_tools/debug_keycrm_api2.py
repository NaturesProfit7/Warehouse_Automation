#!/usr/bin/env python3
"""Debug script for KeyCRM API with different auth methods."""

import asyncio
import httpx
import os
from dotenv import load_dotenv
import base64

# Load environment variables
load_dotenv()

async def test_keycrm_auth_methods():
    """Test different KeyCRM authentication methods."""
    
    api_token = os.getenv("KEYCRM_API_TOKEN")
    print(f"Original API Token: {api_token}")
    
    # Try to extract the actual token from the base64-like string
    # The error showed: 1c53f9424f928de75364f1a66cd5a96fc65386bc
    decoded_token = "1c53f9424f928de75364f1a66cd5a96fc65386bc"
    print(f"Extracted token: {decoded_token}")
    
    # Test different authentication methods
    test_configs = [
        {
            "name": "Bearer with original token",
            "headers": {"Authorization": f"Bearer {api_token}"}
        },
        {
            "name": "Bearer with extracted token",
            "headers": {"Authorization": f"Bearer {decoded_token}"}
        },
        {
            "name": "X-Api-Key with original token",
            "headers": {"X-Api-Key": api_token}
        },
        {
            "name": "X-Api-Key with extracted token", 
            "headers": {"X-Api-Key": decoded_token}
        },
        {
            "name": "Api-Token with original token",
            "headers": {"Api-Token": api_token}
        },
        {
            "name": "Api-Token with extracted token",
            "headers": {"Api-Token": decoded_token}
        },
        {
            "name": "Token query parameter",
            "headers": {},
            "params": {"token": api_token}
        },
        {
            "name": "Token extracted query parameter",
            "headers": {},
            "params": {"token": decoded_token}
        },
        {
            "name": "Api_token query parameter",
            "headers": {},
            "params": {"api_token": api_token}
        }
    ]
    
    base_url = "https://api.keycrm.app"
    order_id = 4505
    
    for config in test_configs:
        print(f"\n{'='*60}")
        print(f"Testing: {config['name']}")
        print(f"{'='*60}")
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            **config["headers"]
        }
        
        params = config.get("params", {})
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                url = f"{base_url}/orders/{order_id}"
                response = await client.get(url, headers=headers, params=params)
                
                print(f"Status Code: {response.status_code}")
                print(f"Content-Type: {response.headers.get('Content-Type', 'Not specified')}")
                
                content_type = response.headers.get("Content-Type", "")
                if "application/json" in content_type:
                    try:
                        data = response.json()
                        print(f"✅ SUCCESS! JSON Response keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
                        if isinstance(data, dict) and "id" in data:
                            print(f"Order ID: {data.get('id')}")
                        return config, data
                    except Exception as e:
                        print(f"❌ JSON Parse Error: {e}")
                elif response.status_code != 200:
                    print(f"❌ HTTP Error: {response.status_code}")
                    if response.text:
                        print(f"Error response: {response.text[:200]}")
                else:
                    print(f"❌ HTML response (not authenticated)")
                
        except Exception as e:
            print(f"❌ Request Error: {e}")
    
    print(f"\n{'='*60}")
    print("❌ All authentication methods failed")
    print("The API token might be:")
    print("1. Invalid or expired")
    print("2. For a different API version")
    print("3. Requires additional setup in KeyCRM admin")
    print(f"{'='*60}")

if __name__ == "__main__":
    asyncio.run(test_keycrm_auth_methods())