"""Сервис управления остатками заготовок."""

import hashlib
from datetime import datetime
from uuid import uuid4

from ..core.exceptions import (
    DuplicateMovementError,
    MappingError,
    StockCalculationError,
)
from ..core.models import (
    CurrentStock,
    Movement,
    MovementSourceType,
    MovementType,
    ProductMapping,
    UnmappedItem,
)
from ..integrations.keycrm import KeyCRMOrder, KeyCRMOrderItem
from ..integrations.sheets import SheetsClient, get_sheets_client
from ..utils.logger import get_logger

logger = get_logger(__name__)


class StockService:
    """Сервис для управления остатками заготовок."""

    def __init__(self, sheets_client: SheetsClient | None = None):
        self.sheets_client = sheets_client or get_sheets_client()
        self._mapping_cache: list[ProductMapping] | None = None
        self._cache_updated: datetime | None = None

        logger.info("StockService initialized")

    async def process_order_movement(
        self,
        order: KeyCRMOrder,
        source_type: MovementSourceType = MovementSourceType.KEYCRM_WEBHOOK
    ) -> list[Movement]:
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
            skipped_items = []

            for item in order.items:
                try:
                    # Проверяем, является ли товар адресником
                    if not self._is_address_tag_product(item):
                        skipped_items.append(item)
                        logger.info(
                            "Item skipped - not an address tag",
                            product_name=item.product_name,
                            order_id=order.id,
                            item_id=item.id
                        )
                        continue

                    # Поиск маппинга для адресников
                    mapping = self._find_mapping_for_item(item)
                    if not mapping:
                        # Сохраняем unmapped item (только для адресников)
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

                    if self._movement_exists(movement_hash):
                        logger.warning(
                            "Movement already exists",
                            order_id=order.id,
                            item_id=item.id,
                            hash=movement_hash
                        )
                        raise DuplicateMovementError(f"Movement already exists: {movement_hash}")

                    # Расчет остатка после движения
                    current_stock = self.get_current_stock(mapping.blank_sku)
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
                self._save_movements(movements)
                self._update_current_stock(movements)

            # Сохранение unmapped items
            if unmapped_items:
                self._save_unmapped_items(unmapped_items)

            logger.info(
                "Order movements processed",
                order_id=order.id,
                movements_created=len(movements),
                unmapped_items=len(unmapped_items),
                skipped_items=len(skipped_items),
                total_items=len(order.items)
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
        note: str | None = None,
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
            current_stock = self.get_current_stock(blank_sku)
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
            self._save_movements([movement])
            self._update_current_stock([movement])

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
            current_stock = self.get_current_stock(blank_sku)
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
            self._save_movements([movement])
            self._update_current_stock([movement])

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

    def get_current_stock(self, blank_sku: str) -> CurrentStock:
        """
        Получение текущего остатка заготовки.
        
        Args:
            blank_sku: Код заготовки
            
        Returns:
            CurrentStock: Текущий остаток
        """
        try:
            # Попытка получения из Current_Stock листа
            current_stock = self.sheets_client.get_current_stock(blank_sku)

            if current_stock:
                return current_stock

            # Если записи нет, создаем с нулевым остатком (НЕ сохраняем сразу)
            logger.info("Creating new stock record", blank_sku=blank_sku)

            new_stock = CurrentStock(
                blank_sku=blank_sku,
                on_hand=0,
                reserved=0,
                available=0,
                last_updated=datetime.now()
            )

            # НЕ сохраняем сразу - сохранение произойдет в _update_current_stock
            return new_stock

        except Exception as e:
            logger.error("Failed to get current stock", blank_sku=blank_sku, error=str(e))
            raise StockCalculationError(f"Failed to get stock for {blank_sku}: {str(e)}")

    async def get_all_current_stock(self) -> list[CurrentStock]:
        """Получение всех текущих остатков."""
        try:
            return self.sheets_client.get_all_current_stock()
        except Exception as e:
            logger.error("Failed to get all current stock", error=str(e))
            raise StockCalculationError(f"Failed to get all stock: {str(e)}")

    def _find_mapping_for_item(self, item: KeyCRMOrderItem) -> ProductMapping | None:
        """Поиск маппинга для товара заказа."""

        try:
            mappings = self._get_product_mappings()

            # Извлекаем свойства товара (маппинг украинских названий из KeyCRM)
            product_name = item.product_name.strip()

            # Для размера проверяем и "Розмір" и "Форма" (для фигурных адресников)
            size_property = (item.properties.get("Розмір", "") or
                           item.properties.get("Форма", "")).strip()

            metal_color = item.properties.get("Колір", "").strip()     # "Колір" из KeyCRM

            # Поиск по приоритету (сначала точное совпадение)
            best_match = None
            highest_priority = 0

            for mapping in mappings:
                if not mapping.active:
                    continue

                # Проверка совпадения (если поле в маппинге пустое - считаем подходящим)
                name_match = mapping.product_name.strip().lower() == product_name.lower()

                # Size совпадение (если пусто в маппинге - подходит любой)
                size_match = (not mapping.size_property.strip() or
                             mapping.size_property.strip().lower() == size_property.lower())

                # Color совпадение (если пусто в маппинге - подходит любой)
                color_match = (not mapping.metal_color.strip() or
                              mapping.metal_color.strip().lower() == metal_color.lower())

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

    def _is_address_tag_product(self, item: KeyCRMOrderItem) -> bool:
        """
        Проверка, является ли товар адресником.
        
        Args:
            item: Товар из KeyCRM заказа
            
        Returns:
            bool: True если товар является адресником
        """
        product_name = item.product_name.lower().strip()

        # Ключевые слова для адресников
        address_tag_keywords = [
            "адресник",  # основное слово
            "жетон",     # альтернативное название
            "медальон"   # еще одно возможное название
        ]

        # Проверяем наличие ключевых слов
        for keyword in address_tag_keywords:
            if keyword in product_name:
                logger.debug(
                    "Product identified as address tag",
                    product_name=item.product_name,
                    keyword=keyword
                )
                return True

        logger.debug(
            "Product is not an address tag",
            product_name=item.product_name
        )
        return False

    def _get_product_mappings(self) -> list[ProductMapping]:
        """Получение маппингов с кешированием."""

        # Кеш на 5 минут
        if (self._mapping_cache is not None and
            self._cache_updated is not None and
            (datetime.now() - self._cache_updated).total_seconds() < 300):
            return self._mapping_cache

        try:
            logger.debug("Refreshing mapping cache")
            self._mapping_cache = self.sheets_client.get_product_mappings()
            self._cache_updated = datetime.now()

            logger.info("Mapping cache refreshed", count=len(self._mapping_cache))
            return self._mapping_cache

        except Exception as e:
            logger.error("Failed to get product mappings", error=str(e))
            raise MappingError(f"Failed to get mappings: {str(e)}")

    def _suggest_sku_for_item(self, item: KeyCRMOrderItem) -> str | None:
        """Предположение SKU для unmapped товара."""

        try:
            product_name = item.product_name.lower()
            properties = item.properties

            # Определение типа (сначала проверяем конкретные формы)
            if "кістка" in product_name or "bone" in product_name:
                sku_type = "BONE"
            elif "бублик" in product_name or "ring" in product_name:
                sku_type = "RING"
            elif "круглий" in product_name or "round" in product_name:
                sku_type = "ROUND"
            # Для фигурных - сначала проверяем конкретную форму
            elif "квітка" in str(properties) or "квітка" in product_name:
                sku_type = "FLOWER"
            elif "хмарка" in str(properties) or "хмарка" in product_name:
                sku_type = "CLOUD"
            elif "серце" in str(properties) or "серце" in product_name:
                sku_type = "HEART"
            elif "фігурний" in product_name:  # Общий случай для фигурных
                sku_type = "HEART"  # По умолчанию сердце
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

    def _movement_exists(self, movement_hash: str) -> bool:
        """Проверка существования движения по хешу."""
        return self.sheets_client.movement_exists(movement_hash)

    def _save_movements(self, movements: list[Movement]) -> None:
        """Сохранение движений в Google Sheets."""
        self.sheets_client.add_movements(movements)

    def _update_current_stock(self, movements: list[Movement]) -> None:
        """Обновление текущих остатков на основе движений."""

        # Группируем движения по SKU
        stock_updates: dict[str, int] = {}

        for movement in movements:
            if movement.blank_sku not in stock_updates:
                stock_updates[movement.blank_sku] = 0
            stock_updates[movement.blank_sku] += movement.qty

        # Обновляем остатки
        updated_stocks = []

        for blank_sku, qty_change in stock_updates.items():
            current_stock = self.get_current_stock(blank_sku)

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
        self.sheets_client.update_current_stock(updated_stocks)

    def _save_unmapped_items(self, unmapped_items: list[UnmappedItem]) -> None:
        """Сохранение unmapped позиций."""
        self.sheets_client.add_unmapped_items(unmapped_items)
    
    async def update_usage_statistics(self) -> int:
        """
        Обновление статистики использования для всех SKU.
        
        Returns:
            int: Количество обновленных SKU
        """
        try:
            logger.info("Updating usage statistics for all SKUs")
            
            # Получаем все движения
            all_movements = self.sheets_client.get_movements()
            
            # Получаем текущие остатки
            current_stocks = await self.get_all_current_stock()
            
            # Создаем словарь для накопления статистики
            sku_stats = {}
            
            from datetime import datetime, timedelta
            cutoff_date = datetime.now() - timedelta(days=30)  # За последние 30 дней
            
            # Анализируем движения за последние 30 дней
            for movement in all_movements:
                if movement.timestamp < cutoff_date:
                    continue
                    
                sku = movement.blank_sku
                if sku not in sku_stats:
                    sku_stats[sku] = {
                        'total_outbound': 0,
                        'days_with_usage': set(),
                        'last_order_date': None,
                        'last_receipt_date': None
                    }
                
                if movement.type == MovementType.ORDER and movement.qty < 0:
                    sku_stats[sku]['total_outbound'] += abs(movement.qty)
                    sku_stats[sku]['days_with_usage'].add(movement.timestamp.date())
                    sku_stats[sku]['last_order_date'] = max(
                        sku_stats[sku]['last_order_date'] or movement.timestamp.date(),
                        movement.timestamp.date()
                    )
                elif movement.type == MovementType.RECEIPT and movement.qty > 0:
                    sku_stats[sku]['last_receipt_date'] = max(
                        sku_stats[sku]['last_receipt_date'] or movement.timestamp.date(),
                        movement.timestamp.date()
                    )
            
            # Обновляем статистику текущих остатков
            updated_stocks = []
            
            for stock in current_stocks:
                sku = stock.blank_sku
                stats = sku_stats.get(sku, {})
                
                # Рассчитываем средний дневной расход
                total_outbound = stats.get('total_outbound', 0)
                days_with_usage = len(stats.get('days_with_usage', set()))
                
                if days_with_usage > 0:
                    # Средний расход в дни с активностью
                    avg_daily_usage = total_outbound / 30  # Равномерно за 30 дней
                else:
                    avg_daily_usage = 0.0
                
                # Рассчитываем дни до исчерпания
                days_of_stock = None
                if avg_daily_usage > 0:
                    days_of_stock = int(stock.on_hand / avg_daily_usage)
                
                # Обновляем объект
                stock.avg_daily_usage = round(avg_daily_usage, 2)
                stock.days_of_stock = days_of_stock
                stock.last_order_date = stats.get('last_order_date')
                stock.last_receipt_date = stats.get('last_receipt_date')
                stock.last_updated = datetime.now()
                
                updated_stocks.append(stock)
            
            # Сохраняем обновленные данные
            if updated_stocks:
                self.sheets_client.update_current_stock(updated_stocks)
            
            logger.info(
                "Usage statistics updated successfully", 
                updated_skus=len(updated_stocks),
                analyzed_movements=len([m for m in all_movements if m.timestamp >= cutoff_date])
            )
            
            return len(updated_stocks)
            
        except Exception as e:
            logger.error("Failed to update usage statistics", error=str(e))
            raise StockCalculationError(f"Usage statistics update failed: {str(e)}")


# Глобальный экземпляр сервиса
_stock_service: StockService | None = None


def get_stock_service() -> StockService:
    """Получение глобального экземпляра Stock Service."""
    global _stock_service

    if _stock_service is None:
        _stock_service = StockService()

    return _stock_service
