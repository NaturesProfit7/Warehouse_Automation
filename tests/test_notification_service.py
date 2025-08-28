"""Тесты для сервиса уведомлений."""

import pytest
from datetime import datetime, date, timedelta
from unittest.mock import Mock, AsyncMock, patch

from src.services.notification_service import NotificationService, NotificationConfig
from src.core.models import CurrentStock, ReplenishmentRecommendation, UrgencyLevel, MasterBlank


@pytest.fixture
def notification_service():
    """Фикстура сервиса уведомлений."""
    service = NotificationService()
    # Мокаем зависимости
    service.stock_service = Mock()
    service.sheets_client = Mock()
    service.stock_calculator = Mock()
    return service


@pytest.fixture
def mock_critical_stocks():
    """Мок критичных остатков."""
    return [
        CurrentStock(
            blank_sku="BLK-BONE-30-GLD",
            on_hand=10,
            available=10,
            last_updated=datetime.now()
        ),
        CurrentStock(
            blank_sku="BLK-RING-25-SIL", 
            on_hand=5,
            available=5,
            last_updated=datetime.now()
        )
    ]


@pytest.fixture
def mock_master_blanks():
    """Мок справочника заготовок."""
    return [
        MasterBlank(
            blank_sku="BLK-BONE-30-GLD",
            type="BONE",
            size_mm=30,
            color="GLD",
            name_ua="Кістка",
            min_stock=50,
            par_stock=150
        ),
        MasterBlank(
            blank_sku="BLK-RING-25-SIL",
            type="RING", 
            size_mm=25,
            color="SIL",
            name_ua="Бублик",
            min_stock=100,
            par_stock=300
        )
    ]


@pytest.fixture
def mock_critical_recommendations():
    """Мок критичных рекомендаций."""
    return [
        ReplenishmentRecommendation(
            blank_sku="BLK-BONE-30-GLD",
            on_hand=10,
            min_level=50,
            reorder_point=50,
            target_level=150,
            need_order=True,
            recommended_qty=147,  # (150-10)*1.05
            urgency=UrgencyLevel.CRITICAL,
            estimated_stockout=date.today() + timedelta(days=2),
            last_calculated=datetime.now()
        ),
        ReplenishmentRecommendation(
            blank_sku="BLK-RING-25-SIL",
            on_hand=5,
            min_level=100,
            reorder_point=100,
            target_level=300,
            need_order=True,
            recommended_qty=310,
            urgency=UrgencyLevel.CRITICAL,
            estimated_stockout=date.today() + timedelta(days=1),
            last_calculated=datetime.now()
        )
    ]


class TestNotificationService:
    """Тесты сервиса уведомлений."""
    
    def test_notification_config_defaults(self):
        """Тест настроек по умолчанию."""
        config = NotificationConfig()
        
        assert config.critical_threshold_hours == 1
        assert config.high_threshold_hours == 8
        assert config.daily_summary_enabled is True
        assert config.daily_summary_hour == 9
        assert config.min_critical_items == 1
        assert config.max_items_per_message == 10
    
    @pytest.mark.asyncio
    async def test_check_critical_stock_no_items(self, notification_service):
        """Тест проверки когда нет критичных остатков."""
        # Мокаем пустые результаты
        notification_service.stock_service.get_all_current_stock = AsyncMock(return_value=[])
        notification_service.sheets_client.get_master_blanks.return_value = []
        notification_service.stock_calculator.calculate_replenishment_needs.return_value = []
        
        result = await notification_service.check_critical_stock()
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_check_critical_stock_below_minimum(self, notification_service, mock_critical_stocks, 
                                                    mock_master_blanks, mock_critical_recommendations):
        """Тест проверки критичных остатков."""
        # Настраиваем моки
        notification_service.stock_service.get_all_current_stock = AsyncMock(return_value=mock_critical_stocks)
        notification_service.sheets_client.get_master_blanks.return_value = mock_master_blanks
        notification_service.stock_calculator.calculate_replenishment_needs.return_value = mock_critical_recommendations
        
        result = await notification_service.check_critical_stock()
        
        assert result is not None
        assert result.alert_type == "critical_stock"
        assert len(result.critical_items) == 2
        assert result.total_items_count == 2
        assert "КРИТИЧНЫЕ ОСТАТКИ" in result.message
    
    @pytest.mark.asyncio
    async def test_send_telegram_alert_no_token(self, notification_service):
        """Тест отправки без токена."""
        with patch('src.services.notification_service.settings') as mock_settings:
            mock_settings.TELEGRAM_BOT_TOKEN = None
            
            from src.services.notification_service import CriticalStockAlert
            alert = CriticalStockAlert(
                alert_type="test",
                timestamp=datetime.now(),
                critical_items=[],
                high_priority_items=[],
                total_items_count=0,
                message="Test message"
            )
            
            result = await notification_service.send_telegram_alert(alert)
            assert result is False
    
    @pytest.mark.asyncio 
    async def test_send_telegram_alert_no_admins(self, notification_service):
        """Тест отправки без администраторов."""
        with patch('src.services.notification_service.settings') as mock_settings:
            mock_settings.TELEGRAM_BOT_TOKEN = "test_token"
            mock_settings.TELEGRAM_ADMIN_USERS = []
            
            from src.services.notification_service import CriticalStockAlert
            alert = CriticalStockAlert(
                alert_type="test",
                timestamp=datetime.now(),
                critical_items=[],
                high_priority_items=[],
                total_items_count=0,
                message="Test message"
            )
            
            result = await notification_service.send_telegram_alert(alert)
            assert result is False
    
    @pytest.mark.asyncio
    async def test_generate_daily_summary(self, notification_service, mock_critical_stocks, mock_master_blanks):
        """Тест генерации ежедневной сводки."""
        # Мокаем данные
        notification_service.stock_service.get_all_current_stock = AsyncMock(return_value=mock_critical_stocks)
        notification_service.sheets_client.get_master_blanks.return_value = mock_master_blanks
        
        mock_recommendations = [
            ReplenishmentRecommendation(
                blank_sku="BLK-BONE-30-GLD",
                on_hand=10,
                min_level=50,
                reorder_point=50,
                target_level=150,
                need_order=True,
                recommended_qty=147,
                urgency=UrgencyLevel.CRITICAL,
                last_calculated=datetime.now()
            )
        ]
        notification_service.stock_calculator.calculate_replenishment_needs.return_value = mock_recommendations
        
        result = await notification_service.generate_daily_summary()
        
        assert result is not None
        assert "Ежедневная сводка склада" in result
        assert "Всего SKU: 2" in result
        assert "Критичные: 1" in result
        assert "Используйте /analytics" in result
    
    def test_should_send_critical_alert_first_time(self, notification_service):
        """Тест первой отправки уведомления."""
        mock_critical = [Mock(urgency=UrgencyLevel.CRITICAL)]
        mock_high = []
        
        result = notification_service._should_send_critical_alert(mock_critical, mock_high)
        assert result is True
    
    def test_should_send_critical_alert_too_soon(self, notification_service):
        """Тест блокировки частых уведомлений."""
        # Устанавливаем недавнее уведомление
        notification_service._last_alerts["critical_stock"] = datetime.now() - timedelta(minutes=30)
        
        mock_critical = [Mock(urgency=UrgencyLevel.CRITICAL)]
        mock_high = []
        
        result = notification_service._should_send_critical_alert(mock_critical, mock_high)
        assert result is False  # Слишком рано для критичного (< 1 час)
    
    def test_should_send_critical_alert_time_passed(self, notification_service):
        """Тест отправки после прошедшего времени."""
        # Устанавливаем старое уведомление
        notification_service._last_alerts["critical_stock"] = datetime.now() - timedelta(hours=2)
        
        mock_critical = [Mock(urgency=UrgencyLevel.CRITICAL)]
        mock_high = []
        
        result = notification_service._should_send_critical_alert(mock_critical, mock_high)
        assert result is True  # Прошло достаточно времени
    
    def test_format_critical_alert_message(self, notification_service):
        """Тест форматирования сообщения об алерте."""
        critical_item = ReplenishmentRecommendation(
            blank_sku="BLK-BONE-30-GLD",
            on_hand=10,
            min_level=50,
            reorder_point=50,
            target_level=150,
            need_order=True,
            recommended_qty=147,
            urgency=UrgencyLevel.CRITICAL,
            estimated_stockout=date.today() + timedelta(days=2),
            last_calculated=datetime.now()
        )
        
        high_item = ReplenishmentRecommendation(
            blank_sku="BLK-RING-25-SIL",
            on_hand=35,
            min_level=50,
            reorder_point=50,
            target_level=150,
            need_order=True,
            recommended_qty=120,
            urgency=UrgencyLevel.HIGH,
            last_calculated=datetime.now()
        )
        
        result = notification_service._format_critical_alert_message([critical_item], [high_item])
        
        assert "КРИТИЧНЫЕ ОСТАТКИ!" in result
        assert "Критичные (1):" in result
        assert "BLK-BONE-30-GLD" in result
        assert "10 шт" in result
        assert "2д. до исчерпания" in result
        assert "Важные (1):" in result
        assert "BLK-RING-25-SIL" in result
        assert "/analytics" in result


@pytest.mark.asyncio 
async def test_notification_service_integration():
    """Интеграционный тест сервиса уведомлений."""
    from src.services.notification_service import get_notification_service
    
    # Получаем глобальный экземпляр
    service1 = get_notification_service()
    service2 = get_notification_service()
    
    # Должен быть один и тот же объект
    assert service1 is service2
    assert isinstance(service1, NotificationService)