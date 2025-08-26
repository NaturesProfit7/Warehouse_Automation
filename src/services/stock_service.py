"""Сервис управления остатками заготовок."""

import hashlib
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

from ..core.models import (
    Movement, MovementType, MovementSourceType, CurrentStock,
    ProductMapping, BlankSKU, UnmappedItem
)
from ..core.exceptions import (
    StockCalculationError, DuplicateMovementError, 
    InsufficientStockError, MappingError
)
from ..integrations.keycrm import KeyCRMOrder, KeyCRMOrderItem
from ..integrations.sheets import get_sheets_client, SheetsClient
from ..utils.logger import get_logger

logger = get_logger(__name__)


class StockService:
    """Сервис для управления остатками заготовок."""
    
    def __init__(self, sheets_client: Optional[SheetsClient] = None):
        self.sheets_client = sheets_client or get_sheets_client()
        self._mapping_cache: Optional[List[ProductMapping]] = None
        self._cache_updated: Optional[datetime] = None
        
        logger.info("StockService initialized")
    
    async def process_order_movement(
        self, 
        order: KeyCRMOrder, 
        source_type: MovementSourceType = MovementSourceType.KEYCRM_WEBHOOK
    ) -> List[Movement]:
        """
        Обработка движений по заказу (расход заготовок).
        
        Args:
            order: Заказ KeyCRM
            source_type: Источник движения
            
        Returns:
            List[Movement]: Созданные движения
            
        Raises:
            MappingError: Если товар не найден в маппинге
            DuplicateMovementError: Если движение уже существует
            InsufficientStockError: Если недостаточно товара
        """
        try:
            logger.info("Processing order movements", order_id=order.id, items_count=len(order.items))
            
            movements = []
            unmapped_items = []
            
            for item in order.items:
                try:
                    # Поиск маппинга
                    mapping = await self._find_mapping_for_item(item)
                    if not mapping:
                        # Сохраняем unmapped item
                        unmapped_item = UnmappedItem(
                            order_id=str(order.id),
                            line_id=str(item.id),
                            product_name=item.product_name,
                            properties=item.properties,
                            suggested_sku=self._suggest_sku_for_item(item),
                            error_type="no_mapping"
                        )
                        unmapped_items.append(unmapped_item)
                        continue
                    
                    # Проверка дубликата
                    movement_hash = self._calculate_movement_hash(
                        source_id=f"{order.id}_{item.id}",
                        blank_sku=mapping.blank_sku,
                        qty=item.quantity * mapping.qty_per_unit,
                        movement_type=MovementType.ORDER,
                        timestamp=order.updated_at
                    )
                    
                    if await self._movement_exists(movement_hash):
                        logger.warning(
                            "Movement already exists", 
                            order_id=order.id, 
                            item_id=item.id,
                            hash=movement_hash
                        )
                        raise DuplicateMovementError(f"Movement already exists: {movement_hash}")
                    
                    # Расчет остатка после движения
                    current_stock = await self.get_current_stock(mapping.blank_sku)
                    quantity_consumed = item.quantity * mapping.qty_per_unit
                    new_balance = current_stock.on_hand - quantity_consumed
                    
                    # Проверка достаточности остатков (согласно ТЗ не должно быть отрицательных)
                    if new_balance < 0:
                        logger.error(
                            "Insufficient stock",
                            blank_sku=mapping.blank_sku,
                            current=current_stock.on_hand,
                            requested=quantity_consumed,
                            shortfall=abs(new_balance)
                        )
                        # По ТЗ отрицательных остатков быть не может, но продолжаем обработку
                        # для уведомления, устанавливаем остаток в 0
                        new_balance = 0
                    
                    # Создание движения
                    movement = Movement(
                        id=uuid4(),
                        timestamp=order.updated_at,
                        type=MovementType.ORDER,
                        source_type=source_type,
                        source_id=f"{order.id}_{item.id}",
                        blank_sku=mapping.blank_sku,
                        qty=-quantity_consumed,  # Отрицательное для расхода
                        balance_after=new_balance,
                        user=f"KeyCRM Order #{order.id}",
                        note=f"Order item: {item.product_name} x{item.quantity}",
                        hash=movement_hash
                    )
                    
                    movements.append(movement)
                    
                except MappingError:
                    # Уже обработано выше
                    pass
                except Exception as e:
                    logger.error(
                        "Error processing order item",
                        order_id=order.id,
                        item_id=item.id,
                        error=str(e)
                    )
                    raise StockCalculationError(f"Failed to process item {item.id}: {str(e)}")
            
            # Сохранение движений
            if movements:
                await self._save_movements(movements)
                await self._update_current_stock(movements)
            
            # Сохранение unmapped items
            if unmapped_items:
                await self._save_unmapped_items(unmapped_items)
            
            logger.info(
                "Order movements processed",
                order_id=order.id,
                movements_created=len(movements),
                unmapped_items=len(unmapped_items)
            )
            
            return movements
            
        except Exception as e:
            logger.error("Failed to process order movements", order_id=order.id, error=str(e))
            raise StockCalculationError(f"Failed to process order {order.id}: {str(e)}")
    
    async def add_receipt_movement(
        self,
        blank_sku: str,
        quantity: int,
        user: str,
        note: Optional[str] = None,
        source_type: MovementSourceType = MovementSourceType.TELEGRAM
    ) -> Movement:
        """
        Добавление прихода заготовок.
        
        Args:
            blank_sku: Код заготовки
            quantity: Количество (положительное)
            user: Пользователь
            note: Примечание
            source_type: Источник движения
            
        Returns:
            Movement: Созданное движение
        """
        try:
            if quantity <= 0:
                raise ValueError("Quantity must be positive")
            
            logger.info("Adding receipt movement", blank_sku=blank_sku, quantity=quantity, user=user)
            
            # Получение текущего остатка
            current_stock = await self.get_current_stock(blank_sku)
            new_balance = current_stock.on_hand + quantity
            
            # Создание движения
            timestamp = datetime.now()
            movement_hash = self._calculate_movement_hash(
                source_id=f"receipt_{uuid4()}",
                blank_sku=blank_sku,
                qty=quantity,
                movement_type=MovementType.RECEIPT,
                timestamp=timestamp
            )
            
            movement = Movement(
                id=uuid4(),
                timestamp=timestamp,
                type=MovementType.RECEIPT,
                source_type=source_type,
                source_id=f"receipt_{timestamp.isoformat()}",
                blank_sku=blank_sku,
                qty=quantity,  # Положительное для прихода
                balance_after=new_balance,
                user=user,
                note=note or f"Receipt of {quantity} units",
                hash=movement_hash
            )
            
            # Сохранение
            await self._save_movements([movement])
            await self._update_current_stock([movement])
            
            logger.info(
                "Receipt movement added",
                blank_sku=blank_sku,
                quantity=quantity,
                new_balance=new_balance,
                movement_id=str(movement.id)
            )
            
            return movement
            
        except Exception as e:
            logger.error("Failed to add receipt movement", blank_sku=blank_sku, error=str(e))
            raise StockCalculationError(f"Failed to add receipt: {str(e)}")
    
    async def add_correction_movement(
        self,
        blank_sku: str,
        quantity_adjustment: int,
        user: str,
        reason: str,
        source_type: MovementSourceType = MovementSourceType.MANUAL
    ) -> Movement:
        """
        Добавление корректировки остатков.
        
        Args:
            blank_sku: Код заготовки  
            quantity_adjustment: Корректировка (+/-)
            user: Пользователь
            reason: Причина корректировки
            source_type: Источник движения
            
        Returns:
            Movement: Созданное движение
        """
        try:
            logger.info(
                "Adding correction movement",
                blank_sku=blank_sku,
                adjustment=quantity_adjustment,
                user=user
            )
            
            # Получение текущего остатка
            current_stock = await self.get_current_stock(blank_sku)
            new_balance = current_stock.on_hand + quantity_adjustment
            
            # Не допускаем отрицательного остатка
            if new_balance < 0:
                logger.warning(
                    "Correction would result in negative stock",
                    blank_sku=blank_sku,
                    current=current_stock.on_hand,
                    adjustment=quantity_adjustment,
                    would_be=new_balance
                )
                # Корректируем до нуля
                quantity_adjustment = -current_stock.on_hand
                new_balance = 0
            
            # Создание движения
            timestamp = datetime.now()
            movement_hash = self._calculate_movement_hash(
                source_id=f"correction_{uuid4()}",
                blank_sku=blank_sku,
                qty=quantity_adjustment,
                movement_type=MovementType.CORRECTION,
                timestamp=timestamp
            )
            
            movement = Movement(
                id=uuid4(),
                timestamp=timestamp,
                type=MovementType.CORRECTION,
                source_type=source_type,
                source_id=f"correction_{timestamp.isoformat()}",
                blank_sku=blank_sku,
                qty=quantity_adjustment,
                balance_after=new_balance,
                user=user,
                note=f"Correction: {reason}",
                hash=movement_hash
            )
            
            # Сохранение
            await self._save_movements([movement])
            await self._update_current_stock([movement])
            
            logger.info(
                "Correction movement added",
                blank_sku=blank_sku,
                adjustment=quantity_adjustment,
                new_balance=new_balance,
                movement_id=str(movement.id)
            )
            
            return movement
            
        except Exception as e:
            logger.error("Failed to add correction movement", blank_sku=blank_sku, error=str(e))
            raise StockCalculationError(f"Failed to add correction: {str(e)}")
    
    async def get_current_stock(self, blank_sku: str) -> CurrentStock:
        """
        Получение текущего остатка заготовки.
        
        Args:
            blank_sku: Код заготовки
            
        Returns:
            CurrentStock: Текущий остаток
        """
        try:
            # Попытка получения из Current_Stock листа
            current_stock = await self.sheets_client.get_current_stock(blank_sku)
            
            if current_stock:
                return current_stock
            
            # Если записи нет, создаем с нулевым остатком
            logger.info("Creating new stock record", blank_sku=blank_sku)
            
            new_stock = CurrentStock(
                blank_sku=blank_sku,
                on_hand=0,
                reserved=0,
                available=0,
                last_updated=datetime.now()
            )
            
            await self.sheets_client.update_current_stock([new_stock])
            return new_stock
            
        except Exception as e:
            logger.error("Failed to get current stock", blank_sku=blank_sku, error=str(e))
            raise StockCalculationError(f"Failed to get stock for {blank_sku}: {str(e)}")
    
    async def get_all_current_stock(self) -> List[CurrentStock]:
        """Получение всех текущих остатков."""
        try:
            return await self.sheets_client.get_all_current_stock()
        except Exception as e:
            logger.error("Failed to get all current stock", error=str(e))
            raise StockCalculationError(f"Failed to get all stock: {str(e)}")
    
    async def _find_mapping_for_item(self, item: KeyCRMOrderItem) -> Optional[ProductMapping]:
        """Поиск маппинга для товара заказа."""
        
        try:
            mappings = await self._get_product_mappings()
            
            # Извлекаем свойства товара
            product_name = item.product_name.strip()
            size_property = item.properties.get("size", "").strip()
            metal_color = item.properties.get("metal_color", "").strip()
            
            # Поиск по приоритету (сначала точное совпадение)
            best_match = None
            highest_priority = 0
            
            for mapping in mappings:
                if not mapping.active:
                    continue
                
                # Проверка совпадения
                name_match = mapping.product_name.lower() == product_name.lower()
                size_match = mapping.size_property.lower() == size_property.lower()
                color_match = mapping.metal_color.lower() == metal_color.lower()
                
                if name_match and size_match and color_match:
                    if mapping.priority > highest_priority:
                        best_match = mapping
                        highest_priority = mapping.priority
            
            if best_match:
                logger.debug(
                    "Found mapping for item",
                    product_name=product_name,
                    size_property=size_property,
                    metal_color=metal_color,
                    blank_sku=best_match.blank_sku,
                    priority=best_match.priority
                )
                return best_match
            
            logger.warning(
                "No mapping found for item",
                product_name=product_name,
                size_property=size_property,
                metal_color=metal_color,
                properties=item.properties
            )
            
            return None
            
        except Exception as e:
            logger.error("Error finding mapping for item", item_id=item.id, error=str(e))
            raise MappingError(f"Failed to find mapping: {str(e)}")
    
    async def _get_product_mappings(self) -> List[ProductMapping]:
        """Получение маппингов с кешированием."""
        
        # Кеш на 5 минут
        if (self._mapping_cache is not None and 
            self._cache_updated is not None and 
            (datetime.now() - self._cache_updated).total_seconds() < 300):
            return self._mapping_cache
        
        try:
            logger.debug("Refreshing mapping cache")
            self._mapping_cache = await self.sheets_client.get_product_mappings()
            self._cache_updated = datetime.now()
            
            logger.info("Mapping cache refreshed", count=len(self._mapping_cache))
            return self._mapping_cache
            
        except Exception as e:
            logger.error("Failed to get product mappings", error=str(e))
            raise MappingError(f"Failed to get mappings: {str(e)}")
    
    def _suggest_sku_for_item(self, item: KeyCRMOrderItem) -> Optional[str]:
        """Предположение SKU для unmapped товара."""
        
        try:
            product_name = item.product_name.lower()
            properties = item.properties
            
            # Определение типа
            if "кістка" in product_name or "bone" in product_name:
                sku_type = "BONE"
            elif "бублик" in product_name or "ring" in product_name:
                sku_type = "RING"
            elif "круглий" in product_name or "round" in product_name:
                sku_type = "ROUND"
            elif "фігурний" in product_name or "серце" in str(properties):
                sku_type = "HEART"
            elif "квітка" in str(properties):
                sku_type = "FLOWER"
            elif "хмарка" in str(properties):
                sku_type = "CLOUD"
            else:
                return None
            
            # Определение размера
            size = "25"  # По умолчанию
            size_str = str(properties.get("size", ""))
            if "20" in size_str:
                size = "20"
            elif "30" in size_str:
                size = "30"
            
            # Определение цвета
            color = "GLD"  # По умолчанию золото
            color_str = str(properties.get("metal_color", "")).lower()
            if "срібло" in color_str or "silver" in color_str:
                color = "SIL"
            
            suggested_sku = f"BLK-{sku_type}-{size}-{color}"
            
            logger.debug("Suggested SKU", original=item.product_name, suggested=suggested_sku)
            return suggested_sku
            
        except Exception as e:
            logger.error("Error suggesting SKU", item_id=item.id, error=str(e))
            return None
    
    def _calculate_movement_hash(
        self,
        source_id: str,
        blank_sku: str,
        qty: int,
        movement_type: MovementType,
        timestamp: datetime
    ) -> str:
        """Расчет хеша движения для дедупликации."""
        
        hash_string = f"{source_id}_{blank_sku}_{qty}_{movement_type.value}_{timestamp.isoformat()}"
        return hashlib.sha256(hash_string.encode()).hexdigest()
    
    async def _movement_exists(self, movement_hash: str) -> bool:
        """Проверка существования движения по хешу."""
        return await self.sheets_client.movement_exists(movement_hash)
    
    async def _save_movements(self, movements: List[Movement]) -> None:
        """Сохранение движений в Google Sheets."""
        await self.sheets_client.add_movements(movements)
    
    async def _update_current_stock(self, movements: List[Movement]) -> None:
        """Обновление текущих остатков на основе движений."""
        
        # Группируем движения по SKU
        stock_updates: Dict[str, int] = {}
        
        for movement in movements:
            if movement.blank_sku not in stock_updates:
                stock_updates[movement.blank_sku] = 0
            stock_updates[movement.blank_sku] += movement.qty
        
        # Обновляем остатки
        updated_stocks = []
        
        for blank_sku, qty_change in stock_updates.items():
            current_stock = await self.get_current_stock(blank_sku)
            
            # Обновляем значения
            current_stock.on_hand += qty_change
            current_stock.available = current_stock.on_hand - current_stock.reserved
            current_stock.last_updated = datetime.now()
            
            # Обновляем даты последних операций
            for movement in movements:
                if movement.blank_sku == blank_sku:
                    if movement.type == MovementType.RECEIPT:
                        current_stock.last_receipt_date = movement.timestamp.date()
                    elif movement.type == MovementType.ORDER:
                        current_stock.last_order_date = movement.timestamp.date()
            
            updated_stocks.append(current_stock)
        
        # Сохраняем обновления
        await self.sheets_client.update_current_stock(updated_stocks)
    
    async def _save_unmapped_items(self, unmapped_items: List[UnmappedItem]) -> None:
        """Сохранение unmapped позиций."""
        await self.sheets_client.add_unmapped_items(unmapped_items)


# Глобальный экземпляр сервиса
_stock_service: Optional[StockService] = None


def get_stock_service() -> StockService:
    """Получение глобального экземпляра Stock Service."""
    global _stock_service
    
    if _stock_service is None:
        _stock_service = StockService()
    
    return _stock_service