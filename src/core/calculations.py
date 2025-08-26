"""Расчеты пополнения и управления остатками (простой режим)."""

from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Tuple

from .models import (
    CurrentStock, MasterBlank, ReplenishmentRecommendation,
    UrgencyLevel
)
from .exceptions import StockCalculationError
from ..config import settings
from ..utils.logger import get_logger

logger = get_logger(__name__)


class StockCalculator:
    """Калькулятор остатков в простом режиме (MIN/PAR)."""
    
    def __init__(self):
        self.lead_time_days = settings.LEAD_TIME_DAYS
        self.scrap_pct = settings.SCRAP_PCT
        self.target_cover_days = settings.TARGET_COVER_DAYS
        
        logger.info(
            "Stock calculator initialized",
            mode="simple",
            lead_time_days=self.lead_time_days,
            scrap_pct=self.scrap_pct,
            target_cover_days=self.target_cover_days
        )
    
    def calculate_replenishment_needs(
        self,
        current_stocks: List[CurrentStock],
        master_blanks: List[MasterBlank]
    ) -> List[ReplenishmentRecommendation]:
        """
        Расчет потребности в пополнении (простой режим).
        
        Args:
            current_stocks: Текущие остатки
            master_blanks: Справочник заготовок с MIN/PAR уровнями
            
        Returns:
            List[ReplenishmentRecommendation]: Рекомендации по закупке
        """
        
        try:
            logger.info(
                "Starting replenishment calculation",
                current_stocks_count=len(current_stocks),
                master_blanks_count=len(master_blanks)
            )
            
            # Создаем словарь master blanks для быстрого поиска
            master_dict = {blank.blank_sku: blank for blank in master_blanks}
            
            recommendations = []
            
            for stock in current_stocks:
                try:
                    # Находим master blank для данного SKU
                    master = master_dict.get(stock.blank_sku)
                    if not master or not master.active:
                        logger.debug(
                            "Skipping inactive or unknown SKU",
                            blank_sku=stock.blank_sku
                        )
                        continue
                    
                    # Расчет рекомендации
                    recommendation = self._calculate_sku_recommendation(stock, master)
                    recommendations.append(recommendation)
                    
                except Exception as e:
                    logger.error(
                        "Error calculating recommendation for SKU",
                        blank_sku=stock.blank_sku,
                        error=str(e)
                    )
                    continue
            
            # Сортируем по приоритету (критичные первыми)
            recommendations.sort(key=self._get_urgency_priority)
            
            logger.info(
                "Replenishment calculation completed",
                total_recommendations=len(recommendations),
                need_order=sum(1 for r in recommendations if r.need_order),
                critical=sum(1 for r in recommendations if r.urgency == UrgencyLevel.CRITICAL)
            )
            
            return recommendations
            
        except Exception as e:
            logger.error("Failed to calculate replenishment needs", error=str(e))
            raise StockCalculationError(f"Replenishment calculation failed: {str(e)}")
    
    def _calculate_sku_recommendation(
        self,
        stock: CurrentStock,
        master: MasterBlank
    ) -> ReplenishmentRecommendation:
        """Расчет рекомендации для одного SKU."""
        
        # В простом режиме reorder_point = min_level
        reorder_point = master.min_stock
        target_level = master.par_stock
        
        # Основная логика: нужен заказ если остаток <= минимума
        need_order = stock.on_hand <= reorder_point
        
        # Расчет рекомендуемого количества
        if need_order:
            # Заказываем до целевого уровня с учетом брака
            base_qty = target_level - stock.on_hand
            recommended_qty = int(base_qty * (1 + self.scrap_pct))
        else:
            recommended_qty = 0
        
        # Определение приоритета
        urgency = self._calculate_urgency(stock.on_hand, reorder_point)
        
        # Прогноз исчерпания (упрощенный)
        estimated_stockout = self._estimate_stockout_date(stock)
        
        recommendation = ReplenishmentRecommendation(
            blank_sku=stock.blank_sku,
            on_hand=stock.on_hand,
            min_level=master.min_stock,
            reorder_point=reorder_point,
            target_level=target_level,
            need_order=need_order,
            recommended_qty=recommended_qty,
            urgency=urgency,
            estimated_stockout=estimated_stockout,
            last_calculated=datetime.now()
        )
        
        logger.debug(
            "SKU recommendation calculated",
            blank_sku=stock.blank_sku,
            on_hand=stock.on_hand,
            min_level=master.min_stock,
            need_order=need_order,
            recommended_qty=recommended_qty,
            urgency=urgency.value
        )
        
        return recommendation
    
    def _calculate_urgency(self, on_hand: int, min_level: int) -> UrgencyLevel:
        """
        Определение приоритета закупки.
        
        Args:
            on_hand: Текущий остаток
            min_level: Минимальный уровень
            
        Returns:
            UrgencyLevel: Уровень приоритета
        """
        
        if on_hand <= min_level * 0.5:
            return UrgencyLevel.CRITICAL
        elif on_hand <= min_level * 0.7:
            return UrgencyLevel.HIGH
        elif on_hand <= min_level:
            return UrgencyLevel.MEDIUM
        else:
            return UrgencyLevel.LOW
    
    def _estimate_stockout_date(self, stock: CurrentStock) -> Optional[date]:
        """
        Упрощенный прогноз даты исчерпания.
        
        Args:
            stock: Текущий остаток
            
        Returns:
            Optional[date]: Прогнозируемая дата исчерпания
        """
        
        try:
            # Если есть средний дневной расход, используем его
            if stock.avg_daily_usage > 0:
                days_remaining = stock.on_hand / stock.avg_daily_usage
                return date.today() + timedelta(days=int(days_remaining))
            
            # Если нет статистики, используем days_of_stock если есть
            if stock.days_of_stock:
                return date.today() + timedelta(days=stock.days_of_stock)
            
            # Иначе возвращаем None
            return None
            
        except Exception:
            return None
    
    def _get_urgency_priority(self, recommendation: ReplenishmentRecommendation) -> int:
        """Получение числового приоритета для сортировки."""
        
        priority_map = {
            UrgencyLevel.CRITICAL: 0,
            UrgencyLevel.HIGH: 1,
            UrgencyLevel.MEDIUM: 2,
            UrgencyLevel.LOW: 3
        }
        
        return priority_map.get(recommendation.urgency, 4)
    
    def calculate_stock_metrics(
        self,
        current_stocks: List[CurrentStock],
        master_blanks: List[MasterBlank]
    ) -> Dict[str, any]:
        """
        Расчет общих метрик по складу.
        
        Args:
            current_stocks: Текущие остатки  
            master_blanks: Справочник заготовок
            
        Returns:
            Dict[str, any]: Метрики склада
        """
        
        try:
            # Создаем словарь master blanks
            master_dict = {blank.blank_sku: blank for blank in master_blanks if blank.active}
            
            # Базовые метрики
            total_skus = len(master_dict)
            skus_with_stock = 0
            skus_below_min = 0
            skus_critical = 0
            total_value_estimate = 0
            total_units = 0
            
            for stock in current_stocks:
                master = master_dict.get(stock.blank_sku)
                if not master:
                    continue
                
                total_units += stock.on_hand
                
                if stock.on_hand > 0:
                    skus_with_stock += 1
                
                if stock.on_hand <= master.min_stock:
                    skus_below_min += 1
                
                if stock.on_hand <= master.min_stock * 0.5:
                    skus_critical += 1
                
                # Примерная оценка стоимости (можно улучшить)
                # Пока используем упрощенную формулу
                estimated_unit_cost = 10  # примерная стоимость единицы в грн
                total_value_estimate += stock.on_hand * estimated_unit_cost
            
            # Расчет оборачиваемости (упрощенный)
            avg_turnover = 0
            turnover_count = 0
            
            for stock in current_stocks:
                if stock.avg_daily_usage > 0 and stock.on_hand > 0:
                    daily_turnover = stock.avg_daily_usage / stock.on_hand
                    avg_turnover += daily_turnover * 365  # годовая оборачиваемость
                    turnover_count += 1
            
            avg_turnover = avg_turnover / max(turnover_count, 1)
            
            # Риск дефицита
            stockout_risk = (skus_below_min / max(total_skus, 1)) * 100
            
            metrics = {
                "calculation_date": date.today(),
                "total_skus": total_skus,
                "skus_with_stock": skus_with_stock,
                "skus_below_min": skus_below_min,
                "skus_critical": skus_critical,
                "total_units": total_units,
                "total_value_estimate": round(total_value_estimate, 2),
                "avg_turnover": round(avg_turnover, 2),
                "stockout_risk_pct": round(stockout_risk, 2),
                "stock_coverage_pct": round((skus_with_stock / max(total_skus, 1)) * 100, 2)
            }
            
            logger.info("Stock metrics calculated", **metrics)
            return metrics
            
        except Exception as e:
            logger.error("Failed to calculate stock metrics", error=str(e))
            raise StockCalculationError(f"Stock metrics calculation failed: {str(e)}")
    
    def analyze_stock_position(
        self,
        blank_sku: str,
        current_stock: CurrentStock,
        master_blank: MasterBlank
    ) -> Dict[str, any]:
        """
        Детальный анализ позиции одного SKU.
        
        Args:
            blank_sku: Код заготовки
            current_stock: Текущий остаток
            master_blank: Справочник заготовки
            
        Returns:
            Dict[str, any]: Детальный анализ
        """
        
        try:
            # Базовые показатели
            stock_level_pct = (current_stock.on_hand / max(master_blank.par_stock, 1)) * 100
            
            # Определение статуса
            if current_stock.on_hand <= master_blank.min_stock * 0.5:
                status = "critical"
                status_message = "Критично низкий уровень"
            elif current_stock.on_hand <= master_blank.min_stock:
                status = "low" 
                status_message = "Ниже минимума"
            elif current_stock.on_hand <= master_blank.par_stock * 0.8:
                status = "normal"
                status_message = "Нормальный уровень"
            else:
                status = "high"
                status_message = "Высокий уровень"
            
            # Рекомендации
            recommendation = self._calculate_sku_recommendation(current_stock, master_blank)
            
            # Прогнозы
            days_until_min = None
            if current_stock.avg_daily_usage > 0:
                remaining_above_min = current_stock.on_hand - master_blank.min_stock
                if remaining_above_min > 0:
                    days_until_min = remaining_above_min / current_stock.avg_daily_usage
            
            analysis = {
                "blank_sku": blank_sku,
                "current_stock": current_stock.on_hand,
                "min_level": master_blank.min_stock,
                "par_level": master_blank.par_stock,
                "stock_level_pct": round(stock_level_pct, 1),
                "status": status,
                "status_message": status_message,
                "need_order": recommendation.need_order,
                "recommended_qty": recommendation.recommended_qty,
                "urgency": recommendation.urgency.value,
                "days_until_min": int(days_until_min) if days_until_min else None,
                "estimated_stockout": recommendation.estimated_stockout,
                "last_receipt_date": current_stock.last_receipt_date,
                "last_order_date": current_stock.last_order_date,
                "avg_daily_usage": current_stock.avg_daily_usage
            }
            
            logger.debug("Stock position analyzed", blank_sku=blank_sku, status=status)
            return analysis
            
        except Exception as e:
            logger.error("Failed to analyze stock position", blank_sku=blank_sku, error=str(e))
            raise StockCalculationError(f"Stock position analysis failed: {str(e)}")


# Глобальный экземпляр калькулятора
_stock_calculator: Optional[StockCalculator] = None


def get_stock_calculator() -> StockCalculator:
    """Получение глобального экземпляра калькулятора остатков."""
    global _stock_calculator
    
    if _stock_calculator is None:
        _stock_calculator = StockCalculator()
    
    return _stock_calculator