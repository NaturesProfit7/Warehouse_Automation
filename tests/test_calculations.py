"""Тесты для калькулятора остатков."""

import pytest
from datetime import datetime, date, timedelta

from src.core.calculations import StockCalculator
from src.core.models import (
    CurrentStock, MasterBlank, ReplenishmentRecommendation,
    UrgencyLevel, BlankType, BlankColor
)


class TestStockCalculator:
    """Тесты StockCalculator."""
    
    @pytest.fixture
    def calculator(self):
        """Экземпляр калькулятора."""
        return StockCalculator()
    
    @pytest.fixture
    def sample_master_blank(self):
        """Образец справочника заготовки."""
        return MasterBlank(
            blank_sku="BLK-RING-25-GLD",
            type=BlankType.RING,
            size_mm=25,
            color=BlankColor.GOLD,
            name_ua="бублик 25мм золото",
            min_stock=100,
            par_stock=300,
            active=True
        )
    
    @pytest.fixture
    def sample_current_stock_normal(self):
        """Нормальный остаток."""
        return CurrentStock(
            blank_sku="BLK-RING-25-GLD",
            on_hand=150,
            reserved=0,
            available=150,
            avg_daily_usage=5.0,
            last_updated=datetime.now()
        )
    
    @pytest.fixture
    def sample_current_stock_critical(self):
        """Критически низкий остаток."""
        return CurrentStock(
            blank_sku="BLK-RING-25-GLD",
            on_hand=45,  # Меньше 50% от минимума (100)
            reserved=0,
            available=45,
            avg_daily_usage=3.0,
            last_updated=datetime.now()
        )
    
    @pytest.fixture
    def sample_current_stock_high(self):
        """Высокий остаток."""
        return CurrentStock(
            blank_sku="BLK-RING-25-GLD",
            on_hand=250,
            reserved=0,
            available=250,
            avg_daily_usage=2.0,
            last_updated=datetime.now()
        )
    
    def test_calculate_sku_recommendation_normal(
        self, 
        calculator, 
        sample_current_stock_normal, 
        sample_master_blank
    ):
        """Тест расчета рекомендации для нормального остатка."""
        
        recommendation = calculator._calculate_sku_recommendation(
            sample_current_stock_normal, 
            sample_master_blank
        )
        
        # Остаток 150 > минимума 100, заказ не нужен
        assert not recommendation.need_order
        assert recommendation.recommended_qty == 0
        assert recommendation.urgency == UrgencyLevel.LOW
        assert recommendation.blank_sku == "BLK-RING-25-GLD"
        assert recommendation.on_hand == 150
        assert recommendation.min_level == 100
        assert recommendation.target_level == 300
    
    def test_calculate_sku_recommendation_critical(
        self, 
        calculator, 
        sample_current_stock_critical, 
        sample_master_blank
    ):
        """Тест расчета рекомендации для критического остатка."""
        
        recommendation = calculator._calculate_sku_recommendation(
            sample_current_stock_critical, 
            sample_master_blank
        )
        
        # Остаток 45 <= минимума 100, нужен заказ
        assert recommendation.need_order
        assert recommendation.recommended_qty > 0
        assert recommendation.urgency == UrgencyLevel.CRITICAL
        
        # Проверяем расчет количества с учетом брака (5%)
        base_qty = 300 - 45  # target - current
        expected_qty = int(base_qty * 1.05)  # +5% на брак
        assert recommendation.recommended_qty == expected_qty
    
    def test_calculate_sku_recommendation_high_stock(
        self, 
        calculator, 
        sample_current_stock_high, 
        sample_master_blank
    ):
        """Тест расчета для высокого остатка."""
        
        recommendation = calculator._calculate_sku_recommendation(
            sample_current_stock_high, 
            sample_master_blank
        )
        
        # Остаток 250 > минимума 100, заказ не нужен
        assert not recommendation.need_order
        assert recommendation.recommended_qty == 0
        assert recommendation.urgency == UrgencyLevel.LOW
    
    def test_calculate_urgency_levels(self, calculator):
        """Тест определения уровней приоритета."""
        
        min_level = 100
        
        # Критичный: <= 50% от минимума
        urgency = calculator._calculate_urgency(45, min_level)
        assert urgency == UrgencyLevel.CRITICAL
        
        # Высокий: <= 70% от минимума  
        urgency = calculator._calculate_urgency(65, min_level)
        assert urgency == UrgencyLevel.HIGH
        
        # Средний: <= минимума
        urgency = calculator._calculate_urgency(95, min_level)
        assert urgency == UrgencyLevel.MEDIUM
        
        # Низкий: > минимума
        urgency = calculator._calculate_urgency(150, min_level)
        assert urgency == UrgencyLevel.LOW
    
    def test_estimate_stockout_date_with_usage(self, calculator):
        """Тест прогноза исчерпания при наличии статистики расхода."""
        
        stock = CurrentStock(
            blank_sku="TEST-SKU",
            on_hand=60,
            reserved=0,
            available=60,
            avg_daily_usage=3.0,  # 3 единицы в день
            last_updated=datetime.now()
        )
        
        estimated_date = calculator._estimate_stockout_date(stock)
        
        # Должно быть примерно через 20 дней (60/3)
        expected_date = date.today() + timedelta(days=20)
        assert estimated_date == expected_date
    
    def test_estimate_stockout_date_without_usage(self, calculator):
        """Тест прогноза исчерпания без статистики расхода."""
        
        stock = CurrentStock(
            blank_sku="TEST-SKU",
            on_hand=60,
            reserved=0,
            available=60,
            avg_daily_usage=0,  # Нет статистики
            last_updated=datetime.now()
        )
        
        estimated_date = calculator._estimate_stockout_date(stock)
        
        # Без статистики должно быть None
        assert estimated_date is None
    
    def test_calculate_replenishment_needs(
        self, 
        calculator, 
        sample_master_blank
    ):
        """Тест расчета потребности в пополнении для списка остатков."""
        
        # Создаем разные остатки
        stocks = [
            CurrentStock(
                blank_sku="BLK-RING-25-GLD",
                on_hand=45,  # Критично низкий
                reserved=0,
                available=45,
                last_updated=datetime.now()
            ),
            CurrentStock(
                blank_sku="BLK-RING-25-SIL", 
                on_hand=150,  # Нормальный
                reserved=0,
                available=150,
                last_updated=datetime.now()
            )
        ]
        
        # Создаем справочник для второго SKU
        master_blanks = [
            sample_master_blank,
            MasterBlank(
                blank_sku="BLK-RING-25-SIL",
                type=BlankType.RING,
                size_mm=25, 
                color=BlankColor.SILVER,
                name_ua="бублик 25мм срібло",
                min_stock=100,
                par_stock=300,
                active=True
            )
        ]
        
        recommendations = calculator.calculate_replenishment_needs(stocks, master_blanks)
        
        # Проверяем что получили рекомендации для всех позиций
        assert len(recommendations) == 2
        
        # Проверяем сортировку по приоритету (критичные первыми)
        assert recommendations[0].urgency == UrgencyLevel.CRITICAL
        assert recommendations[0].need_order == True
        assert recommendations[1].urgency == UrgencyLevel.LOW
        assert recommendations[1].need_order == False
    
    def test_calculate_stock_metrics(
        self, 
        calculator, 
        sample_master_blank
    ):
        """Тест расчета общих метрик склада."""
        
        # Подготавливаем данные
        stocks = [
            CurrentStock(
                blank_sku="BLK-RING-25-GLD",
                on_hand=45,  # Ниже минимума
                reserved=0,
                available=45,
                avg_daily_usage=2.0,
                last_updated=datetime.now()
            ),
            CurrentStock(
                blank_sku="BLK-RING-25-SIL",
                on_hand=150,  # Норма
                reserved=0,
                available=150,
                avg_daily_usage=3.0,
                last_updated=datetime.now()
            )
        ]
        
        master_blanks = [
            sample_master_blank,
            MasterBlank(
                blank_sku="BLK-RING-25-SIL",
                type=BlankType.RING,
                size_mm=25,
                color=BlankColor.SILVER,
                name_ua="бублик 25мм срібло",
                min_stock=100,
                par_stock=300,
                active=True
            )
        ]
        
        metrics = calculator.calculate_stock_metrics(stocks, master_blanks)
        
        # Проверяем основные метрики
        assert metrics["total_skus"] == 2
        assert metrics["skus_with_stock"] == 2  # Оба с остатками
        assert metrics["skus_below_min"] == 1  # Один ниже минимума
        assert metrics["skus_critical"] == 1  # Один критичный
        assert metrics["total_units"] == 195  # 45 + 150
        assert metrics["stockout_risk_pct"] == 50.0  # 1 из 2 = 50%
        assert metrics["stock_coverage_pct"] == 100.0  # 2 из 2 = 100%
    
    def test_analyze_stock_position(
        self, 
        calculator,
        sample_current_stock_critical,
        sample_master_blank
    ):
        """Тест детального анализа позиции SKU."""
        
        analysis = calculator.analyze_stock_position(
            "BLK-RING-25-GLD",
            sample_current_stock_critical,
            sample_master_blank
        )
        
        # Проверяем структуру анализа
        assert analysis["blank_sku"] == "BLK-RING-25-GLD"
        assert analysis["current_stock"] == 45
        assert analysis["min_level"] == 100
        assert analysis["par_level"] == 300
        assert analysis["status"] == "critical"
        assert analysis["need_order"] == True
        assert analysis["urgency"] == "critical"
        assert analysis["recommended_qty"] > 0
        
        # Проверяем расчет процентов
        expected_pct = (45 / 300) * 100
        assert analysis["stock_level_pct"] == expected_pct


if __name__ == "__main__":
    pytest.main([__file__, "-v"])