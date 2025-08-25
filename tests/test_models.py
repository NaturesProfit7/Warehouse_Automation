"""Тесты для core моделей."""

import pytest
from datetime import datetime
from uuid import UUID

from src.core.models import (
    BlankSKU, MasterBlank, Movement, MovementType, MovementSourceType,
    BlankType, BlankColor, ProductMapping, CurrentStock, 
    ReplenishmentRecommendation, UrgencyLevel
)
from src.core.validators import (
    validate_blank_sku, parse_blank_sku, generate_blank_sku,
    validate_movement_qty, validate_stock_levels
)
from src.core.exceptions import ValidationError


class TestBlankSKU:
    """Тесты для модели BlankSKU."""
    
    def test_blank_sku_creation(self):
        """Тест создания BlankSKU."""
        sku = BlankSKU(
            blank_sku="BLK-BONE-25-GLD",
            type=BlankType.BONE,
            size_mm=25,
            color=BlankColor.GOLD,
            name_ua="кістка маленька"
        )
        
        assert sku.blank_sku == "BLK-BONE-25-GLD"
        assert sku.type == BlankType.BONE
        assert sku.size_mm == 25
        assert sku.color == BlankColor.GOLD
        assert sku.active is True  # default value

    def test_display_name_property(self):
        """Тест computed property display_name."""
        sku = BlankSKU(
            blank_sku="BLK-HEART-25-SIL",
            type=BlankType.HEART,
            size_mm=25,
            color=BlankColor.SILVER,
            name_ua="серце"
        )
        
        expected = "серце 25мм SIL"
        assert sku.display_name == expected


class TestMasterBlank:
    """Тесты для модели MasterBlank."""
    
    def test_master_blank_defaults(self):
        """Тест значений по умолчанию."""
        blank = MasterBlank(
            blank_sku="BLK-RING-30-GLD",
            type=BlankType.RING,
            size_mm=30,
            color=BlankColor.GOLD,
            name_ua="бублик 30мм"
        )
        
        assert blank.opening_stock == 0
        assert blank.min_stock == 100
        assert blank.par_stock == 300
        assert blank.notes is None


class TestMovement:
    """Тесты для модели Movement."""
    
    def test_movement_creation(self):
        """Тест создания Movement."""
        movement = Movement(
            type=MovementType.RECEIPT,
            source_type=MovementSourceType.TELEGRAM,
            source_id="test_123",
            blank_sku="BLK-BONE-25-GLD",
            qty=100,
            balance_after=300,
            hash="abcd1234"
        )
        
        assert isinstance(movement.id, UUID)
        assert isinstance(movement.timestamp, datetime)
        assert movement.type == MovementType.RECEIPT
        assert movement.qty == 100

    def test_movement_json_serialization(self):
        """Тест JSON сериализации Movement."""
        movement = Movement(
            type=MovementType.ORDER,
            source_type=MovementSourceType.KEYCRM_WEBHOOK,
            source_id="order_456",
            blank_sku="BLK-HEART-25-SIL",
            qty=-2,
            balance_after=48,
            hash="xyz789"
        )
        
        # Проверяем что модель может быть сериализована
        json_data = movement.model_dump()
        assert "id" in json_data
        assert "timestamp" in json_data
        assert json_data["qty"] == -2


class TestProductMapping:
    """Тесты для модели ProductMapping."""
    
    def test_mapping_creation_with_defaults(self):
        """Тест создания маппинга с defaults."""
        mapping = ProductMapping(
            product_name="Адресник фігурний",
            size_property="серце", 
            metal_color="золото",
            blank_sku="BLK-HEART-25-GLD"
        )
        
        assert mapping.qty_per_unit == 1
        assert mapping.active is True
        assert mapping.priority == 50
        assert isinstance(mapping.created_at, datetime)


class TestValidators:
    """Тесты для валидаторов."""
    
    def test_validate_blank_sku_valid(self):
        """Тест валидации правильных SKU."""
        valid_skus = [
            "BLK-BONE-25-GLD",
            "BLK-RING-30-SIL",
            "BLK-ROUND-20-GLD",
            "BLK-HEART-25-SIL",
            "BLK-CLOUD-25-GLD",
            "BLK-FLOWER-25-SIL"
        ]
        
        for sku in valid_skus:
            assert validate_blank_sku(sku) is True

    def test_validate_blank_sku_invalid(self):
        """Тест валидации неправильных SKU."""
        invalid_skus = [
            "BLK-BONE-25",  # Missing color
            "BONE-25-GLD",  # Missing prefix
            "BLK-INVALID-25-GLD",  # Invalid type
            "BLK-BONE-35-GLD",  # Invalid size
            "BLK-BONE-25-RED",  # Invalid color
            "blk-bone-25-gld",  # Wrong case
        ]
        
        for sku in invalid_skus:
            assert validate_blank_sku(sku) is False

    def test_parse_blank_sku(self):
        """Тест парсинга SKU."""
        sku = "BLK-HEART-25-SIL"
        parsed = parse_blank_sku(sku)
        
        expected = {
            "prefix": "BLK",
            "type": "HEART",
            "size": "25",
            "color": "SIL"
        }
        
        assert parsed == expected

    def test_parse_blank_sku_invalid(self):
        """Тест парсинга неправильного SKU."""
        with pytest.raises(ValidationError):
            parse_blank_sku("INVALID-SKU")

    def test_generate_blank_sku(self):
        """Тест генерации SKU."""
        sku = generate_blank_sku("CLOUD", 25, "GLD")
        assert sku == "BLK-CLOUD-25-GLD"

    def test_generate_blank_sku_invalid(self):
        """Тест генерации неправильного SKU."""
        with pytest.raises(ValidationError):
            generate_blank_sku("INVALID", 25, "GLD")

    def test_validate_movement_qty_receipt(self):
        """Тест валидации количества для прихода."""
        assert validate_movement_qty(100, MovementType.RECEIPT) is True
        
        with pytest.raises(ValidationError):
            validate_movement_qty(-50, MovementType.RECEIPT)

    def test_validate_movement_qty_order(self):
        """Тест валидации количества для расхода."""
        assert validate_movement_qty(-5, MovementType.ORDER) is True
        
        with pytest.raises(ValidationError):
            validate_movement_qty(10, MovementType.ORDER)

    def test_validate_movement_qty_limits(self):
        """Тест лимитов количества."""
        with pytest.raises(ValidationError):
            validate_movement_qty(15000, MovementType.RECEIPT)

    def test_validate_stock_levels(self):
        """Тест валидации уровней остатков."""
        assert validate_stock_levels(200, 100, 300) is True
        
        # Отрицательный остаток
        with pytest.raises(ValidationError):
            validate_stock_levels(-10, 100, 300)
        
        # Минимум меньше или равен нулю
        with pytest.raises(ValidationError):
            validate_stock_levels(200, 0, 300)
        
        # PAR меньше или равен MIN
        with pytest.raises(ValidationError):
            validate_stock_levels(200, 300, 300)


class TestEnums:
    """Тесты для enum классов."""
    
    def test_movement_type_values(self):
        """Тест значений MovementType."""
        assert MovementType.ORDER.value == "order"
        assert MovementType.RECEIPT.value == "receipt"
        assert MovementType.CORRECTION.value == "correction"

    def test_urgency_level_values(self):
        """Тест значений UrgencyLevel."""
        assert UrgencyLevel.CRITICAL.value == "critical"
        assert UrgencyLevel.HIGH.value == "high"
        assert UrgencyLevel.MEDIUM.value == "medium"
        assert UrgencyLevel.LOW.value == "low"

    def test_blank_type_values(self):
        """Тест значений BlankType."""
        types = [BlankType.BONE, BlankType.RING, BlankType.ROUND, 
                BlankType.HEART, BlankType.CLOUD, BlankType.FLOWER]
        
        assert len(types) == 6
        assert all(isinstance(t, BlankType) for t in types)

    def test_blank_color_values(self):
        """Тест значений BlankColor."""
        assert BlankColor.GOLD.value == "GLD"
        assert BlankColor.SILVER.value == "SIL"


class TestReplenishmentRecommendation:
    """Тесты для модели ReplenishmentRecommendation."""
    
    def test_replenishment_creation(self):
        """Тест создания рекомендации."""
        rec = ReplenishmentRecommendation(
            blank_sku="BLK-BONE-25-GLD",
            on_hand=80,
            min_level=100,
            reorder_point=100,
            target_level=300,
            need_order=True,
            recommended_qty=220,
            urgency=UrgencyLevel.HIGH
        )
        
        assert rec.need_order is True
        assert rec.recommended_qty == 220
        assert rec.urgency == UrgencyLevel.HIGH
        assert isinstance(rec.last_calculated, datetime)