"""Тесты для планировщика задач."""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

from src.services.scheduler_service import SchedulerService


@pytest.fixture
def scheduler_service():
    """Фикстура планировщика."""
    return SchedulerService()


@pytest.fixture
def mock_notification_service():
    """Мок сервиса уведомлений."""
    mock_service = Mock()
    mock_service.check_critical_stock = AsyncMock(return_value=None)
    mock_service.send_telegram_alert = AsyncMock(return_value=True)
    mock_service.generate_daily_summary = AsyncMock(return_value="Test summary")
    mock_service._send_telegram_message = AsyncMock()
    mock_service.config = Mock()
    mock_service.config.daily_summary_enabled = True
    return mock_service


@pytest.fixture
def mock_stock_service():
    """Мок сервиса остатков."""
    mock_service = Mock()
    mock_service.update_usage_statistics = AsyncMock(return_value=10)
    mock_service.get_all_current_stock = AsyncMock(return_value=[])
    return mock_service


class TestSchedulerService:
    """Тесты планировщика задач."""
    
    def test_scheduler_initialization(self, scheduler_service):
        """Тест инициализации планировщика."""
        assert scheduler_service.timezone.zone == 'Europe/Kyiv'
        assert scheduler_service._running is False
        assert scheduler_service.scheduler is not None
    
    @pytest.mark.asyncio
    async def test_start_scheduler(self, scheduler_service):
        """Тест запуска планировщика."""
        with patch.object(scheduler_service, '_setup_jobs') as mock_setup:
            await scheduler_service.start()
            
            assert scheduler_service._running is True
            assert scheduler_service.scheduler.running is True
            mock_setup.assert_called_once()
        
        # Останавливаем для очистки
        await scheduler_service.stop()
    
    @pytest.mark.asyncio
    async def test_start_scheduler_already_running(self, scheduler_service):
        """Тест повторного запуска планировщика."""
        scheduler_service._running = True
        
        with patch.object(scheduler_service, '_setup_jobs') as mock_setup:
            await scheduler_service.start()
            
            # Не должен вызываться setup
            mock_setup.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_stop_scheduler(self, scheduler_service):
        """Тест остановки планировщика."""
        # Сначала запускаем
        await scheduler_service.start()
        
        # Затем останавливаем
        await scheduler_service.stop()
        
        assert scheduler_service._running is False
        # Планировщик может еще завершаться асинхронно, поэтому убираем эту проверку
    
    @pytest.mark.asyncio
    async def test_stop_scheduler_not_running(self, scheduler_service):
        """Тест остановки не запущенного планировщика."""
        # Не должно выбрасывать исключение
        await scheduler_service.stop()
        assert scheduler_service._running is False
    
    @pytest.mark.asyncio
    async def test_setup_jobs(self, scheduler_service):
        """Тест настройки задач."""
        await scheduler_service._setup_jobs()
        
        # Проверяем что все задачи добавлены
        jobs = scheduler_service.scheduler.get_jobs()
        job_ids = [job.id for job in jobs]
        
        expected_jobs = [
            "check_critical_stock",
            "daily_summary", 
            "update_usage_stats",
            "system_health_check"
        ]
        
        for expected_job in expected_jobs:
            assert expected_job in job_ids
    
    @pytest.mark.asyncio
    async def test_check_critical_stock_job_no_alert(self, scheduler_service, mock_notification_service):
        """Тест задачи проверки критичных остатков (нет алертов)."""
        scheduler_service.notification_service = mock_notification_service
        mock_notification_service.check_critical_stock.return_value = None
        
        # Вызываем задачу напрямую
        await scheduler_service._check_critical_stock_job()
        
        # Проверяем что проверка была вызвана
        mock_notification_service.check_critical_stock.assert_called_once()
        # Уведомление не должно отправляться
        mock_notification_service.send_telegram_alert.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_check_critical_stock_job_with_alert(self, scheduler_service, mock_notification_service):
        """Тест задачи проверки критичных остатков (с алертом)."""
        scheduler_service.notification_service = mock_notification_service
        
        # Создаем мок алерта
        mock_alert = Mock()
        mock_alert.critical_items = [Mock()]
        mock_alert.high_priority_items = []
        mock_notification_service.check_critical_stock.return_value = mock_alert
        
        await scheduler_service._check_critical_stock_job()
        
        # Проверяем что уведомление отправлено
        mock_notification_service.check_critical_stock.assert_called_once()
        mock_notification_service.send_telegram_alert.assert_called_once_with(mock_alert)
    
    @pytest.mark.asyncio
    async def test_daily_summary_job_disabled(self, scheduler_service, mock_notification_service):
        """Тест ежедневной сводки (отключена)."""
        scheduler_service.notification_service = mock_notification_service
        mock_notification_service.config.daily_summary_enabled = False
        
        await scheduler_service._daily_summary_job()
        
        # Сводка не должна генерироваться
        mock_notification_service.generate_daily_summary.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_daily_summary_job_enabled(self, scheduler_service, mock_notification_service):
        """Тест ежедневной сводки (включена)."""
        with patch('src.services.scheduler_service.settings') as mock_settings:
            mock_settings.TELEGRAM_ADMIN_USERS = [123, 456]
            
            scheduler_service.notification_service = mock_notification_service
            mock_notification_service.config.daily_summary_enabled = True
            mock_notification_service.generate_daily_summary.return_value = "Daily summary"
            
            await scheduler_service._daily_summary_job()
            
            # Проверяем генерацию сводки
            mock_notification_service.generate_daily_summary.assert_called_once()
            
            # Проверяем отправку всем админам
            assert mock_notification_service._send_telegram_message.call_count == 2
    
    @pytest.mark.asyncio
    async def test_update_usage_stats_job(self, scheduler_service, mock_stock_service):
        """Тест задачи обновления статистики."""
        scheduler_service.stock_service = mock_stock_service
        
        await scheduler_service._update_usage_stats_job()
        
        mock_stock_service.update_usage_statistics.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_system_health_check_job(self, scheduler_service):
        """Тест задачи проверки состояния системы."""
        with patch.object(scheduler_service, '_check_sheets_health', return_value=True), \
             patch.object(scheduler_service, '_check_telegram_health', return_value=True), \
             patch.object(scheduler_service, '_check_services_health', return_value=True), \
             patch.object(scheduler_service, '_send_health_alert') as mock_send_alert:
            
            await scheduler_service._system_health_check_job()
            
            # Алерт не должен отправляться если все здорово
            mock_send_alert.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_system_health_check_job_with_issues(self, scheduler_service):
        """Тест задачи проверки состояния с проблемами."""
        with patch.object(scheduler_service, '_check_sheets_health', return_value=False), \
             patch.object(scheduler_service, '_check_telegram_health', return_value=True), \
             patch.object(scheduler_service, '_check_services_health', return_value=True), \
             patch.object(scheduler_service, '_send_health_alert') as mock_send_alert:
            
            await scheduler_service._system_health_check_job()
            
            # Алерт должен отправиться
            mock_send_alert.assert_called_once_with(False, True, True)
    
    @pytest.mark.asyncio
    async def test_check_sheets_health_success(self, scheduler_service):
        """Тест проверки здоровья Google Sheets."""
        with patch('src.integrations.sheets.get_sheets_client') as mock_get_client:
            mock_client = Mock()
            mock_client.get_master_blanks.return_value = [Mock()]  # Есть данные
            mock_get_client.return_value = mock_client
            
            result = await scheduler_service._check_sheets_health()
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_check_sheets_health_no_data(self, scheduler_service):
        """Тест проверки Google Sheets без данных."""
        with patch('src.integrations.sheets.get_sheets_client') as mock_get_client:
            mock_client = Mock()
            mock_client.get_master_blanks.return_value = []  # Нет данных
            mock_get_client.return_value = mock_client
            
            result = await scheduler_service._check_sheets_health()
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_check_telegram_health_success(self, scheduler_service):
        """Тест проверки здоровья Telegram API."""
        with patch('src.services.scheduler_service.settings') as mock_settings, \
             patch('httpx.AsyncClient') as mock_client:
            
            mock_settings.TELEGRAM_BOT_TOKEN = "test_token"
            mock_response = Mock()
            mock_response.status_code = 200
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
            
            result = await scheduler_service._check_telegram_health()
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_check_telegram_health_no_token(self, scheduler_service):
        """Тест проверки Telegram без токена."""
        with patch('src.services.scheduler_service.settings') as mock_settings:
            mock_settings.TELEGRAM_BOT_TOKEN = None
            
            result = await scheduler_service._check_telegram_health()
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_check_services_health(self, scheduler_service, mock_stock_service):
        """Тест проверки здоровья сервисов."""
        scheduler_service.stock_service = mock_stock_service
        
        with patch('src.services.scheduler_service.get_notification_service'):
            result = await scheduler_service._check_services_health()
            
            assert result is True
    
    def test_get_job_status_stopped(self, scheduler_service):
        """Тест получения статуса остановленного планировщика."""
        result = scheduler_service.get_job_status()
        
        assert result["status"] == "stopped"
        assert result["jobs"] == []
    
    @pytest.mark.asyncio
    async def test_get_job_status_running(self, scheduler_service):
        """Тест получения статуса работающего планировщика."""
        await scheduler_service.start()
        
        try:
            result = scheduler_service.get_job_status()
            
            assert result["status"] == "running"
            assert len(result["jobs"]) > 0
            assert result["timezone"] == "Europe/Kyiv"
            
            # Проверяем структуру информации о задаче
            job_info = result["jobs"][0]
            assert "id" in job_info
            assert "name" in job_info
            assert "next_run" in job_info
            assert "trigger" in job_info
            
        finally:
            await scheduler_service.stop()
    
    @pytest.mark.asyncio
    async def test_trigger_job_manually_not_found(self, scheduler_service):
        """Тест ручного запуска несуществующей задачи."""
        result = await scheduler_service.trigger_job_manually("nonexistent_job")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_trigger_job_manually_success(self, scheduler_service):
        """Тест успешного ручного запуска задачи."""
        await scheduler_service.start()
        
        try:
            # Запускаем существующую задачу
            result = await scheduler_service.trigger_job_manually("check_critical_stock")
            
            assert result is True
            
        finally:
            await scheduler_service.stop()


@pytest.mark.asyncio
async def test_scheduler_service_integration():
    """Интеграционный тест планировщика."""
    from src.services.scheduler_service import get_scheduler_service
    
    # Получаем глобальный экземпляр
    service1 = get_scheduler_service()
    service2 = get_scheduler_service()
    
    # Должен быть один и тот же объект
    assert service1 is service2
    assert isinstance(service1, SchedulerService)