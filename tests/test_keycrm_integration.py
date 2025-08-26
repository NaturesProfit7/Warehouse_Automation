"""Тесты для интеграции с KeyCRM."""

import pytest
import json
import hmac
import hashlib
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from src.integrations.keycrm import KeyCRMClient, KeyCRMOrder, KeyCRMOrderItem
from src.core.models import KeyCRMWebhookPayload
from src.core.exceptions import IntegrationError


class TestKeyCRMClient:
    """Тесты KeyCRM клиента."""
    
    @pytest.fixture
    def keycrm_client(self):
        """Экземпляр KeyCRM клиента."""
        with patch('src.integrations.keycrm.settings') as mock_settings:
            mock_settings.KEYCRM_API_URL = "https://api.keycrm.app"
            mock_settings.KEYCRM_API_TOKEN = "test_token"
            mock_settings.KEYCRM_WEBHOOK_SECRET = "test_secret"
            
            client = KeyCRMClient()
            return client
    
    @pytest.fixture
    def sample_order_response(self):
        """Образец ответа API заказа."""
        return {
            "id": 12345,
            "status": "confirmed",
            "created_at": "2025-08-26T10:00:00Z",
            "updated_at": "2025-08-26T11:00:00Z",
            "client_id": 5678,
            "grand_total": 450.0,
            "client_name": "Тест Клиент",
            "order_items": [
                {
                    "id": 1,
                    "product_id": 100,
                    "product_name": "Адресник бублик",
                    "quantity": 2,
                    "price": 150.0,
                    "total": 300.0,
                    "properties": {
                        "size": "25 мм",
                        "metal_color": "золото"
                    }
                },
                {
                    "id": 2,
                    "product_id": 101,
                    "product_name": "Адресник фігурний",
                    "quantity": 1,
                    "price": 150.0,
                    "total": 150.0,
                    "properties": {
                        "size": "серце",
                        "metal_color": "срібло"
                    }
                }
            ]
        }
    
    @pytest.fixture
    def sample_webhook_payload(self):
        """Образец payload вебхука."""
        return {
            "event": "order.change_order_status",
            "context": {
                "id": 12345,
                "status": "confirmed",
                "client_id": 5678,
                "grand_total": 450.0,
                "created_at": "2025-08-26T10:00:00Z",
                "updated_at": "2025-08-26T11:00:00Z"
            }
        }
    
    def test_parse_order_response(self, keycrm_client, sample_order_response):
        """Тест парсинга ответа API заказа."""
        
        order = keycrm_client._parse_order_response(sample_order_response)
        
        # Проверяем основные поля заказа
        assert order.id == 12345
        assert order.status == "confirmed"
        assert order.client_id == 5678
        assert order.grand_total == 450.0
        assert order.client_name == "Тест Клиент"
        
        # Проверяем позиции заказа
        assert len(order.items) == 2
        
        item1 = order.items[0]
        assert item1.id == 1
        assert item1.product_name == "Адресник бублик"
        assert item1.quantity == 2
        assert item1.price == 150.0
        assert item1.properties["size"] == "25 мм"
        assert item1.properties["metal_color"] == "золото"
        
        item2 = order.items[1]
        assert item2.product_name == "Адресник фігурний"
        assert item2.properties["size"] == "серце"
        assert item2.properties["metal_color"] == "срібло"
    
    def test_parse_webhook_payload(self, keycrm_client, sample_webhook_payload):
        """Тест парсинга payload вебхука."""
        
        webhook_data = keycrm_client.parse_webhook_payload(sample_webhook_payload)
        
        assert isinstance(webhook_data, KeyCRMWebhookPayload)
        assert webhook_data.event == "order.change_order_status"
        assert webhook_data.order_id == 12345
        assert webhook_data.order_status == "confirmed"
        assert webhook_data.context["client_id"] == 5678
    
    def test_parse_webhook_payload_invalid(self, keycrm_client):
        """Тест парсинга некорректного payload."""
        
        invalid_payload = {
            "invalid": "data"
        }
        
        with pytest.raises(IntegrationError):
            keycrm_client.parse_webhook_payload(invalid_payload)
    
    def test_verify_webhook_signature_valid(self, keycrm_client):
        """Тест проверки валидной HMAC подписи."""
        
        payload = b'{"event": "test"}'
        secret = "test_secret"
        
        # Создаем правильную подпись
        signature_hash = hmac.new(
            secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        signature = f"sha256={signature_hash}"
        
        # Проверяем
        is_valid = keycrm_client.verify_webhook_signature(payload, signature)
        assert is_valid == True
    
    def test_verify_webhook_signature_invalid(self, keycrm_client):
        """Тест проверки невалидной подписи."""
        
        payload = b'{"event": "test"}'
        signature = "sha256=invalid_signature"
        
        is_valid = keycrm_client.verify_webhook_signature(payload, signature)
        assert is_valid == False
    
    def test_verify_webhook_signature_wrong_format(self, keycrm_client):
        """Тест проверки подписи в неправильном формате."""
        
        payload = b'{"event": "test"}'
        signature = "invalid_format"
        
        is_valid = keycrm_client.verify_webhook_signature(payload, signature)
        assert is_valid == False
    
    @pytest.mark.asyncio
    async def test_get_order_success(self, keycrm_client, sample_order_response):
        """Тест успешного получения заказа."""
        
        # Мокируем HTTP клиент
        mock_response = Mock()
        mock_response.json.return_value = sample_order_response
        mock_response.raise_for_status = Mock()
        
        with patch.object(keycrm_client.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            
            order = await keycrm_client.get_order(12345)
            
            # Проверяем результат
            assert isinstance(order, KeyCRMOrder)
            assert order.id == 12345
            assert order.status == "confirmed"
            assert len(order.items) == 2
            
            # Проверяем что был вызван правильный endpoint
            mock_get.assert_called_once_with("/orders/12345")
    
    @pytest.mark.asyncio
    async def test_get_order_not_found(self, keycrm_client):
        """Тест получения несуществующего заказа."""
        
        # Мокируем 404 ошибку
        import httpx
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Not found"
        
        mock_error = httpx.HTTPStatusError(
            "Not found", 
            request=Mock(), 
            response=mock_response
        )
        
        with patch.object(keycrm_client.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = mock_error
            
            with pytest.raises(IntegrationError) as exc_info:
                await keycrm_client.get_order(99999)
            
            assert "not found" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_get_confirmed_orders_since(self, keycrm_client):
        """Тест получения подтвержденных заказов."""
        
        from datetime import date
        
        mock_response = Mock()
        mock_response.json.return_value = {
            "orders": [
                {
                    "id": 1,
                    "status": "confirmed",
                    "created_at": "2025-08-26T10:00:00Z",
                    "updated_at": "2025-08-26T11:00:00Z",
                    "client_id": 1,
                    "grand_total": 100.0,
                    "order_items": []
                }
            ]
        }
        mock_response.raise_for_status = Mock()
        
        with patch.object(keycrm_client.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            
            orders = await keycrm_client.get_confirmed_orders_since(date(2025, 8, 20))
            
            # Проверяем результат
            assert len(orders) == 1
            assert orders[0].id == 1
            assert orders[0].status == "confirmed"
            
            # Проверяем параметры запроса
            call_args = mock_get.call_args
            assert call_args[0][0] == "/orders"  # URL
            params = call_args[1]["params"]
            assert params["status"] == "confirmed"
            assert "2025-08-20" in params["start_date"]


class TestWebhookValidation:
    """Тесты валидации вебхук событий."""
    
    def test_validate_keycrm_event_valid(self):
        """Тест валидации корректного события."""
        
        from src.webhook.auth import validate_keycrm_event
        
        payload = {
            "event": "order.change_order_status",
            "context": {
                "id": 12345,
                "status": "confirmed"
            }
        }
        
        is_valid = validate_keycrm_event(payload)
        assert is_valid == True
    
    def test_validate_keycrm_event_wrong_event(self):
        """Тест валидации неправильного события."""
        
        from src.webhook.auth import validate_keycrm_event
        
        payload = {
            "event": "client.created",  # Не то событие
            "context": {
                "id": 12345,
                "status": "confirmed"
            }
        }
        
        is_valid = validate_keycrm_event(payload)
        assert is_valid == False
    
    def test_validate_keycrm_event_wrong_status(self):
        """Тест валидации неправильного статуса."""
        
        from src.webhook.auth import validate_keycrm_event
        
        payload = {
            "event": "order.change_order_status",
            "context": {
                "id": 12345,
                "status": "pending"  # Не confirmed
            }
        }
        
        is_valid = validate_keycrm_event(payload)
        assert is_valid == False
    
    def test_validate_keycrm_event_missing_order_id(self):
        """Тест валидации без ID заказа."""
        
        from src.webhook.auth import validate_keycrm_event
        
        payload = {
            "event": "order.change_order_status",
            "context": {
                # "id": 12345,  # Отсутствует
                "status": "confirmed"
            }
        }
        
        is_valid = validate_keycrm_event(payload)
        assert is_valid == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])