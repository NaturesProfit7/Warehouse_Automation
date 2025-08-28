"""Тесты для сервиса мониторинга."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

from src.services.monitoring_service import MonitoringService, ComponentStatus, ComponentHealth


@pytest.fixture
def monitoring_service():
    """Фикстура сервиса мониторинга."""
    return MonitoringService()


@pytest.fixture
def mock_healthy_response():
    """Мок здорового HTTP ответа."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"result": {"username": "test_bot", "id": 12345}}
    return mock_response


@pytest.fixture 
def mock_error_response():
    """Мок ошибочного HTTP ответа."""
    mock_response = Mock()
    mock_response.status_code = 500
    return mock_response


class TestComponentHealth:
    """Тесты модели состояния компонента."""
    
    def test_component_health_creation(self):
        """Тест создания объекта состояния компонента."""
        health = ComponentHealth(
            name="test_component",
            status=ComponentStatus.HEALTHY,
            response_time_ms=100,
            last_check=datetime.now(),
            details={"version": "1.0"}
        )
        
        assert health.name == "test_component"
        assert health.status == ComponentStatus.HEALTHY
        assert health.response_time_ms == 100
        assert health.details["version"] == "1.0"
    
    def test_component_health_with_error(self):
        """Тест создания объекта с ошибкой."""
        health = ComponentHealth(
            name="failing_component",
            status=ComponentStatus.CRITICAL,
            error_message="Connection failed"
        )
        
        assert health.name == "failing_component"
        assert health.status == ComponentStatus.CRITICAL
        assert health.error_message == "Connection failed"


class TestMonitoringService:
    """Тесты сервиса мониторинга."""
    
    def test_monitoring_service_initialization(self, monitoring_service):
        """Тест инициализации сервиса."""
        assert monitoring_service.start_time is not None
        assert monitoring_service.health_history == []
        assert monitoring_service.max_history_entries == 100
        assert len(monitoring_service.components) == 6  # 6 компонентов для проверки
    
    @pytest.mark.asyncio
    async def test_safe_component_check_success(self, monitoring_service):
        """Тест безопасной проверки компонента (успех)."""
        # Мок функции проверки, которая возвращает ComponentHealth
        async def mock_check():
            return ComponentHealth(
                name="test_component",
                status=ComponentStatus.HEALTHY
            )
        
        result = await monitoring_service._safe_component_check("test_component", mock_check)
        
        assert result.name == "test_component"
        assert result.status == ComponentStatus.HEALTHY
        assert result.response_time_ms is not None
        assert result.last_check is not None
    
    @pytest.mark.asyncio
    async def test_safe_component_check_exception(self, monitoring_service):
        """Тест безопасной проверки компонента (исключение)."""
        # Мок функции проверки, которая выбрасывает исключение
        async def mock_check():
            raise Exception("Test error")
        
        result = await monitoring_service._safe_component_check("test_component", mock_check)
        
        assert result.name == "test_component"
        assert result.status == ComponentStatus.CRITICAL
        assert result.error_message == "Test error"
    
    @pytest.mark.asyncio
    async def test_check_telegram_bot_no_token(self, monitoring_service):
        """Тест проверки Telegram бота без токена."""
        with patch('src.services.monitoring_service.settings') as mock_settings:
            mock_settings.TELEGRAM_BOT_TOKEN = None
            
            result = await monitoring_service._check_telegram_bot()
            
            assert result.name == "telegram_bot"
            assert result.status == ComponentStatus.CRITICAL
            assert "not configured" in result.error_message
    
    @pytest.mark.asyncio
    async def test_check_telegram_bot_healthy(self, monitoring_service, mock_healthy_response):
        """Тест проверки здорового Telegram бота."""
        with patch('src.services.monitoring_service.settings') as mock_settings, \
             patch('httpx.AsyncClient') as mock_client:
            
            mock_settings.TELEGRAM_BOT_TOKEN = "test_token"
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_healthy_response
            
            result = await monitoring_service._check_telegram_bot()
            
            assert result.name == "telegram_bot"
            assert result.status == ComponentStatus.HEALTHY
            assert result.details["bot_username"] == "test_bot"
    
    @pytest.mark.asyncio
    async def test_check_telegram_bot_error(self, monitoring_service, mock_error_response):
        """Тест проверки Telegram бота с ошибкой."""
        with patch('src.services.monitoring_service.settings') as mock_settings, \
             patch('httpx.AsyncClient') as mock_client:
            
            mock_settings.TELEGRAM_BOT_TOKEN = "test_token"
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_error_response
            
            result = await monitoring_service._check_telegram_bot()
            
            assert result.name == "telegram_bot"
            assert result.status == ComponentStatus.CRITICAL
            assert "HTTP 500" in result.error_message
    
    @pytest.mark.asyncio
    async def test_check_google_sheets_healthy(self, monitoring_service):
        """Тест проверки здорового Google Sheets."""
        with patch('src.services.monitoring_service.get_sheets_client') as mock_get_client:
            mock_client = Mock()
            mock_client.get_master_blanks.return_value = [Mock(), Mock()]  # 2 заготовки
            mock_client.get_movements.return_value = [Mock() for _ in range(10)]  # 10 движений
            mock_get_client.return_value = mock_client
            
            result = await monitoring_service._check_google_sheets()
            
            assert result.name == "google_sheets"
            assert result.status == ComponentStatus.HEALTHY
            assert result.details["master_blanks_count"] == 2
            assert result.details["movements_count"] == 10
    
    @pytest.mark.asyncio
    async def test_check_google_sheets_no_data(self, monitoring_service):
        """Тест проверки Google Sheets без данных."""
        with patch('src.services.monitoring_service.get_sheets_client') as mock_get_client:
            mock_client = Mock()
            mock_client.get_master_blanks.return_value = []  # Нет заготовок
            mock_get_client.return_value = mock_client
            
            result = await monitoring_service._check_google_sheets()
            
            assert result.name == "google_sheets"
            assert result.status == ComponentStatus.WARNING
            assert "No master blanks found" in result.error_message
    
    @pytest.mark.asyncio
    async def test_check_stock_service_healthy(self, monitoring_service):
        """Тест проверки здорового сервиса остатков."""
        with patch('src.services.monitoring_service.get_stock_service') as mock_get_service:
            mock_service = Mock()
            mock_service.get_all_current_stock = AsyncMock(return_value=[Mock() for _ in range(5)])
            mock_get_service.return_value = mock_service
            
            result = await monitoring_service._check_stock_service()
            
            assert result.name == "stock_service"
            assert result.status == ComponentStatus.HEALTHY
            assert result.details["stock_items_count"] == 5
    
    def test_calculate_overall_status_all_healthy(self, monitoring_service):
        """Тест расчета общего статуса (все здорово)."""
        components = {
            "comp1": ComponentHealth("comp1", ComponentStatus.HEALTHY),
            "comp2": ComponentHealth("comp2", ComponentStatus.HEALTHY)
        }
        
        result = monitoring_service._calculate_overall_status(components)
        assert result == ComponentStatus.HEALTHY
    
    def test_calculate_overall_status_has_critical(self, monitoring_service):
        """Тест расчета общего статуса (есть критичные)."""
        components = {
            "comp1": ComponentHealth("comp1", ComponentStatus.HEALTHY),
            "comp2": ComponentHealth("comp2", ComponentStatus.CRITICAL)
        }
        
        result = monitoring_service._calculate_overall_status(components)
        assert result == ComponentStatus.CRITICAL
    
    def test_calculate_overall_status_has_warning(self, monitoring_service):
        """Тест расчета общего статуса (есть предупреждения)."""
        components = {
            "comp1": ComponentHealth("comp1", ComponentStatus.HEALTHY),
            "comp2": ComponentHealth("comp2", ComponentStatus.WARNING)
        }
        
        result = monitoring_service._calculate_overall_status(components)
        assert result == ComponentStatus.WARNING
    
    def test_save_to_history(self, monitoring_service):
        """Тест сохранения в историю."""
        from src.services.monitoring_service import SystemHealth
        
        health = SystemHealth(
            overall_status=ComponentStatus.HEALTHY,
            check_timestamp=datetime.now(),
            components={},
            uptime_seconds=100,
            alerts_count=0,
            warnings_count=0
        )
        
        monitoring_service._save_to_history(health)
        
        assert len(monitoring_service.health_history) == 1
        assert monitoring_service.health_history[0] == health
    
    def test_save_to_history_limit(self, monitoring_service):
        """Тест ограничения размера истории."""
        from src.services.monitoring_service import SystemHealth
        
        monitoring_service.max_history_entries = 2
        
        # Добавляем 3 записи
        for i in range(3):
            health = SystemHealth(
                overall_status=ComponentStatus.HEALTHY,
                check_timestamp=datetime.now() + timedelta(seconds=i),
                components={},
                uptime_seconds=100 + i,
                alerts_count=0,
                warnings_count=0
            )
            monitoring_service._save_to_history(health)
        
        # Должно остаться только 2 последние записи
        assert len(monitoring_service.health_history) == 2
        assert monitoring_service.health_history[0].uptime_seconds == 101  # Вторая запись
        assert monitoring_service.health_history[1].uptime_seconds == 102  # Третья запись
    
    def test_get_health_history(self, monitoring_service):
        """Тест получения истории за период."""
        from src.services.monitoring_service import SystemHealth
        
        now = datetime.now()
        
        # Добавляем записи: одну старую, одну новую
        old_health = SystemHealth(
            overall_status=ComponentStatus.HEALTHY,
            check_timestamp=now - timedelta(hours=25),  # Старше 24 часов
            components={},
            uptime_seconds=100,
            alerts_count=0,
            warnings_count=0
        )
        
        new_health = SystemHealth(
            overall_status=ComponentStatus.HEALTHY,
            check_timestamp=now - timedelta(hours=1),   # Младше 24 часов
            components={},
            uptime_seconds=200,
            alerts_count=0,
            warnings_count=0
        )
        
        monitoring_service._save_to_history(old_health)
        monitoring_service._save_to_history(new_health)
        
        # Получаем историю за 24 часа
        history = monitoring_service.get_health_history(24)
        
        # Должна вернуться только новая запись
        assert len(history) == 1
        assert history[0].uptime_seconds == 200
    
    def test_get_system_summary_no_data(self, monitoring_service):
        """Тест получения сводки без данных."""
        result = monitoring_service.get_system_summary()
        
        assert "error" in result
        assert result["error"] == "No health data available"
    
    def test_get_system_summary_with_data(self, monitoring_service):
        """Тест получения сводки с данными."""
        from src.services.monitoring_service import SystemHealth
        
        health = SystemHealth(
            overall_status=ComponentStatus.HEALTHY,
            check_timestamp=datetime.now(),
            components={
                "comp1": ComponentHealth("comp1", ComponentStatus.HEALTHY, response_time_ms=50),
                "comp2": ComponentHealth("comp2", ComponentStatus.WARNING, response_time_ms=200)
            },
            uptime_seconds=3600,  # 1 час
            alerts_count=0,
            warnings_count=1
        )
        
        monitoring_service._save_to_history(health)
        
        result = monitoring_service.get_system_summary()
        
        assert result["overall_status"] == "healthy"
        assert result["uptime_hours"] == 1.0
        assert result["alerts_count"] == 0
        assert result["warnings_count"] == 1
        assert result["total_components"] == 2
        assert result["healthy_components"] == 1
        assert "comp1" in result["component_summary"]
        assert "comp2" in result["component_summary"]


@pytest.mark.asyncio
async def test_monitoring_service_integration():
    """Интеграционный тест сервиса мониторинга."""
    from src.services.monitoring_service import get_monitoring_service
    
    # Получаем глобальный экземпляр
    service1 = get_monitoring_service()
    service2 = get_monitoring_service()
    
    # Должен быть один и тот же объект
    assert service1 is service2
    assert isinstance(service1, MonitoringService)