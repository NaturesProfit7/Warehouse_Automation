"""Интеграционные тесты для проверки работы системы."""

import pytest
import sys
import os
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, date

# Добавляем src в путь для импорта
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))

def test_core_imports():
    """Тест импорта основных модулей."""
    
    # Тестируем импорт core модулей
    try:
        from src.core.models import (
            CurrentStock, MasterBlank, Movement, 
            ReplenishmentRecommendation, UrgencyLevel
        )
        from src.core.exceptions import (
            StockCalculationError, IntegrationError, MappingError
        )
        assert True, "Core modules imported successfully"
    except ImportError as e:
        pytest.fail(f"Failed to import core modules: {e}")


def test_calculations_import_and_basic_functionality():
    """Тест импорта и базового функционала калькулятора."""
    
    try:
        from src.core.calculations import StockCalculator, get_stock_calculator
        from src.core.models import CurrentStock, MasterBlank, BlankType, BlankColor
        
        # Создаем калькулятор
        calculator = StockCalculator()
        assert calculator is not None
        
        # Проверяем глобальный экземпляр
        global_calc = get_stock_calculator()
        assert global_calc is not None
        assert isinstance(global_calc, StockCalculator)
        
    except ImportError as e:
        pytest.fail(f"Failed to import calculations module: {e}")
    except Exception as e:
        pytest.fail(f"Error in calculations functionality: {e}")


def test_keycrm_integration_import():
    """Тест импорта KeyCRM интеграции."""
    
    try:
        from src.integrations.keycrm import KeyCRMClient, KeyCRMOrder, KeyCRMOrderItem
        
        # Проверяем что классы определены
        assert KeyCRMClient is not None
        assert KeyCRMOrder is not None
        assert KeyCRMOrderItem is not None
        
    except ImportError as e:
        pytest.fail(f"Failed to import KeyCRM integration: {e}")


def test_services_import():
    """Тест импорта сервисов."""
    
    try:
        from src.services.stock_service import StockService
        from src.services.report_service import ReportService
        
        assert StockService is not None
        assert ReportService is not None
        
    except ImportError as e:
        pytest.fail(f"Failed to import services: {e}")


def test_webhook_import():
    """Тест импорта webhook модулей."""
    
    try:
        from src.webhook.auth import validate_keycrm_event, verify_hmac_signature
        from src.webhook.handlers import process_keycrm_webhook
        
        assert validate_keycrm_event is not None
        assert verify_hmac_signature is not None
        assert process_keycrm_webhook is not None
        
    except ImportError as e:
        pytest.fail(f"Failed to import webhook modules: {e}")


def test_scheduler_import():
    """Тест импорта планировщика."""
    
    try:
        from src.scheduler.jobs import get_scheduled_jobs, ScheduledJobs
        from src.scheduler.runner import get_scheduler_runner, SchedulerRunner
        
        assert get_scheduled_jobs is not None
        assert ScheduledJobs is not None
        assert get_scheduler_runner is not None
        assert SchedulerRunner is not None
        
    except ImportError as e:
        pytest.fail(f"Failed to import scheduler modules: {e}")


def test_bot_import():
    """Тест импорта телеграм бота."""
    
    try:
        from src.bot.keyboards import get_main_keyboard, get_blank_type_keyboard
        from src.bot.states import ReceiptStates
        
        assert get_main_keyboard is not None
        assert get_blank_type_keyboard is not None
        assert ReceiptStates is not None
        
    except ImportError as e:
        pytest.fail(f"Failed to import bot modules: {e}")


@pytest.mark.asyncio  
async def test_basic_stock_calculations():
    """Тест базовых расчетов остатков."""
    
    try:
        from src.core.calculations import StockCalculator
        from src.core.models import (
            CurrentStock, MasterBlank, BlankType, BlankColor, UrgencyLevel
        )
        
        calculator = StockCalculator()
        
        # Создаем тестовые данные
        master = MasterBlank(
            blank_sku="TEST-SKU",
            type=BlankType.RING,
            size_mm=25,
            color=BlankColor.GOLD,
            name_ua="тест",
            min_stock=100,
            par_stock=300,
            active=True
        )
        
        stock_low = CurrentStock(
            blank_sku="TEST-SKU",
            on_hand=45,  # Критично низкий
            reserved=0,
            available=45,
            last_updated=datetime.now()
        )
        
        stock_normal = CurrentStock(
            blank_sku="TEST-SKU", 
            on_hand=150,  # Нормальный
            reserved=0,
            available=150,
            last_updated=datetime.now()
        )
        
        # Тест критично низкого остатка
        recommendation_low = calculator._calculate_sku_recommendation(stock_low, master)
        assert recommendation_low.need_order == True
        assert recommendation_low.urgency == UrgencyLevel.CRITICAL
        assert recommendation_low.recommended_qty > 0
        
        # Тест нормального остатка
        recommendation_normal = calculator._calculate_sku_recommendation(stock_normal, master)
        assert recommendation_normal.need_order == False
        assert recommendation_normal.urgency == UrgencyLevel.LOW
        assert recommendation_normal.recommended_qty == 0
        
        print("✓ Stock calculations working correctly")
        
    except Exception as e:
        pytest.fail(f"Error in stock calculations: {e}")


def test_webhook_validation():
    """Тест валидации webhook событий."""
    
    try:
        from src.webhook.auth import validate_keycrm_event
        
        # Валидное событие
        valid_payload = {
            "event": "order.change_order_status",
            "context": {
                "id": 12345,
                "status": "confirmed"
            }
        }
        
        # Невалидное событие
        invalid_payload = {
            "event": "client.created",
            "context": {
                "id": 12345
            }
        }
        
        assert validate_keycrm_event(valid_payload) == True
        assert validate_keycrm_event(invalid_payload) == False
        
        print("✓ Webhook validation working correctly")
        
    except Exception as e:
        pytest.fail(f"Error in webhook validation: {e}")


def test_product_mapping_logic():
    """Тест логики маппинга товаров."""
    
    try:
        from src.services.stock_service import StockService
        from src.integrations.keycrm import KeyCRMOrderItem
        from src.core.models import ProductMapping
        
        # Создаем мок клиента
        mock_sheets_client = Mock()
        service = StockService(mock_sheets_client)
        
        # Тестовый товар
        item = KeyCRMOrderItem(
            id=1,
            product_id=100,
            product_name="Адресник бублик",
            quantity=2,
            price=150.0,
            total=300.0,
            properties={"size": "25 мм", "metal_color": "золото"}
        )
        
        # Тестовый маппинг
        mapping = ProductMapping(
            product_name="Адресник бублик",
            size_property="25 мм",
            metal_color="золото", 
            blank_sku="BLK-RING-25-GLD",
            qty_per_unit=1,
            active=True,
            priority=50,
            created_at=datetime.now()
        )
        
        # Тест логики поиска маппинга
        matches = service._find_item_mapping(item, [mapping])
        assert matches is not None
        assert matches.blank_sku == "BLK-RING-25-GLD"
        
        print("✓ Product mapping logic working correctly")
        
    except Exception as e:
        pytest.fail(f"Error in product mapping: {e}")


def test_config_and_settings():
    """Тест настроек и конфигурации."""
    
    try:
        from src.config import settings
        
        # Проверяем что настройки загружаются
        assert hasattr(settings, 'LEAD_TIME_DAYS')
        assert hasattr(settings, 'SCRAP_PCT') 
        assert hasattr(settings, 'TARGET_COVER_DAYS')
        
        # Проверяем типы
        assert isinstance(settings.LEAD_TIME_DAYS, int)
        assert isinstance(settings.SCRAP_PCT, float)
        
        print("✓ Configuration loading correctly")
        
    except Exception as e:
        pytest.fail(f"Error in configuration: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])