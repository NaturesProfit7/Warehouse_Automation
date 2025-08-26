"""Тесты для сервиса управления остатками."""

import pytest
from datetime import datetime, date
from unittest.mock import Mock, AsyncMock, patch

from src.services.stock_service import StockService
from src.core.models import (
    Movement, MovementType, MovementSourceType, CurrentStock,
    ProductMapping, UnmappedItem
)
from src.integrations.keycrm import KeyCRMOrder, KeyCRMOrderItem
from src.core.exceptions import StockCalculationError, MappingError


class TestStockService:
    """Тесты StockService."""
    
    @pytest.fixture
    def mock_sheets_client(self):
        """Мок Google Sheets клиента."""
        client = Mock()
        client.add_movements = AsyncMock()
        client.update_current_stock = AsyncMock()
        client.get_current_stock = AsyncMock()
        client.get_product_mappings = AsyncMock()
        client.movement_exists = AsyncMock(return_value=False)
        client.add_unmapped_items = AsyncMock()
        return client
    
    @pytest.fixture
    def stock_service(self, mock_sheets_client):
        """Сервис с мокированным клиентом."""
        return StockService(mock_sheets_client)
    
    @pytest.fixture
    def sample_order(self):
        """Образец заказа KeyCRM."""
        item = KeyCRMOrderItem(
            id=1,
            product_id=100,
            product_name="Адресник бублик",
            quantity=2,
            price=150.0,
            total=300.0,
            properties={"size": "25 мм", "metal_color": "золото"}
        )
        
        return KeyCRMOrder(
            id=12345,
            status="confirmed",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            client_id=5678,
            grand_total=300.0,
            items=[item]
        )
    
    @pytest.fixture
    def sample_mapping(self):
        """Образец маппинга товара."""
        return ProductMapping(
            product_name="Адресник бублик",
            size_property="25 мм",
            metal_color="золото",
            blank_sku="BLK-RING-25-GLD",
            qty_per_unit=1,
            active=True,
            priority=50,
            created_at=datetime.now()
        )
    
    @pytest.fixture
    def sample_current_stock(self):
        """Образец текущего остатка."""
        return CurrentStock(
            blank_sku="BLK-RING-25-GLD",
            on_hand=150,
            reserved=0,
            available=150,
            last_updated=datetime.now()
        )
    
    @pytest.mark.asyncio
    async def test_process_order_movement_success(
        self, 
        stock_service, 
        sample_order, 
        sample_mapping, 
        sample_current_stock
    ):
        """Тест успешной обработки движения заказа."""
        
        # Настраиваем моки
        stock_service.sheets_client.get_product_mappings.return_value = [sample_mapping]
        stock_service.sheets_client.get_current_stock.return_value = sample_current_stock
        
        # Выполняем обработку
        movements = await stock_service.process_order_movement(sample_order)
        
        # Проверяем результат
        assert len(movements) == 1
        movement = movements[0]
        
        assert movement.blank_sku == "BLK-RING-25-GLD"
        assert movement.qty == -2  # Расход
        assert movement.balance_after == 148  # 150 - 2
        assert movement.type == MovementType.ORDER
        assert movement.source_type == MovementSourceType.KEYCRM_WEBHOOK
        
        # Проверяем вызовы
        stock_service.sheets_client.add_movements.assert_called_once()
        stock_service.sheets_client.update_current_stock.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_order_movement_no_mapping(
        self, 
        stock_service, 
        sample_order
    ):
        """Тест обработки заказа без маппинга."""
        
        # Настраиваем мок - нет маппингов
        stock_service.sheets_client.get_product_mappings.return_value = []
        
        # Выполняем обработку
        movements = await stock_service.process_order_movement(sample_order)
        
        # Проверяем что движений нет
        assert len(movements) == 0
        
        # Проверяем что unmapped items были добавлены
        stock_service.sheets_client.add_unmapped_items.assert_called_once()
        unmapped_items = stock_service.sheets_client.add_unmapped_items.call_args[0][0]
        assert len(unmapped_items) == 1
        assert unmapped_items[0].product_name == "Адресник бублик"
    
    @pytest.mark.asyncio
    async def test_add_receipt_movement(
        self, 
        stock_service, 
        sample_current_stock
    ):
        """Тест добавления прихода."""
        
        # Настраиваем мок
        stock_service.sheets_client.get_current_stock.return_value = sample_current_stock
        
        # Добавляем приход
        movement = await stock_service.add_receipt_movement(
            blank_sku="BLK-RING-25-GLD",
            quantity=50,
            user="test_user",
            note="Test receipt"
        )
        
        # Проверяем результат
        assert movement.blank_sku == "BLK-RING-25-GLD"
        assert movement.qty == 50  # Положительный для прихода
        assert movement.balance_after == 200  # 150 + 50
        assert movement.type == MovementType.RECEIPT
        assert movement.user == "test_user"
        assert movement.note == "Test receipt"
        
        # Проверяем вызовы
        stock_service.sheets_client.add_movements.assert_called_once()
        stock_service.sheets_client.update_current_stock.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_add_receipt_movement_invalid_quantity(self, stock_service):
        """Тест добавления прихода с неверным количеством."""
        
        with pytest.raises(StockCalculationError):
            await stock_service.add_receipt_movement(
                blank_sku="BLK-RING-25-GLD",
                quantity=-10,  # Отрицательное количество
                user="test_user"
            )
    
    @pytest.mark.asyncio
    async def test_add_correction_movement(
        self, 
        stock_service, 
        sample_current_stock
    ):
        """Тест добавления корректировки."""
        
        # Настраиваем мок
        stock_service.sheets_client.get_current_stock.return_value = sample_current_stock
        
        # Добавляем корректировку
        movement = await stock_service.add_correction_movement(
            blank_sku="BLK-RING-25-GLD",
            quantity_adjustment=-10,
            user="admin",
            reason="Inventory correction"
        )
        
        # Проверяем результат
        assert movement.blank_sku == "BLK-RING-25-GLD"
        assert movement.qty == -10
        assert movement.balance_after == 140  # 150 - 10
        assert movement.type == MovementType.CORRECTION
        assert movement.user == "admin"
        assert "Inventory correction" in movement.note
    
    @pytest.mark.asyncio
    async def test_add_correction_prevents_negative_stock(
        self, 
        stock_service
    ):
        """Тест что корректировка не допускает отрицательный остаток."""
        
        # Остаток 50
        current_stock = CurrentStock(
            blank_sku="BLK-RING-25-GLD",
            on_hand=50,
            reserved=0,
            available=50,
            last_updated=datetime.now()
        )
        
        stock_service.sheets_client.get_current_stock.return_value = current_stock
        
        # Пытаемся списать больше чем есть
        movement = await stock_service.add_correction_movement(
            blank_sku="BLK-RING-25-GLD",
            quantity_adjustment=-100,  # Больше чем остаток
            user="admin",
            reason="Test negative prevention"
        )
        
        # Проверяем что списалось только до нуля
        assert movement.qty == -50  # Скорректировано
        assert movement.balance_after == 0  # Не отрицательный
    
    @pytest.mark.asyncio
    async def test_get_current_stock_existing(
        self, 
        stock_service, 
        sample_current_stock
    ):
        """Тест получения существующего остатка."""
        
        # Настраиваем мок
        stock_service.sheets_client.get_current_stock.return_value = sample_current_stock
        
        # Получаем остаток
        result = await stock_service.get_current_stock("BLK-RING-25-GLD")
        
        # Проверяем
        assert result == sample_current_stock
        assert result.blank_sku == "BLK-RING-25-GLD"
        assert result.on_hand == 150
    
    @pytest.mark.asyncio
    async def test_get_current_stock_new(self, stock_service):
        """Тест получения нового остатка (создание записи)."""
        
        # Настраиваем мок - записи нет
        stock_service.sheets_client.get_current_stock.return_value = None
        stock_service.sheets_client.update_current_stock = AsyncMock()
        
        # Получаем остаток
        result = await stock_service.get_current_stock("BLK-NEW-25-GLD")
        
        # Проверяем что создался новый
        assert result.blank_sku == "BLK-NEW-25-GLD"
        assert result.on_hand == 0
        assert result.available == 0
        
        # Проверяем что был сохранен
        stock_service.sheets_client.update_current_stock.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])