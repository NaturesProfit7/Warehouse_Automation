"""Google Sheets клиент для работы с данными системы."""

import json
from datetime import date, datetime
from typing import Any

import gspread
from google.oauth2.service_account import Credentials
from gspread.exceptions import APIError, WorksheetNotFound

from ..config import settings
from ..core.exceptions import GoogleSheetsError, RetryableError
from ..core.models import (
    CurrentStock,
    MasterBlank,
    Movement,
    ProductMapping,
    ReplenishmentRecommendation,
    UnmappedItem,
)
from ..utils.logger import get_logger
from ..utils.retry import google_sheets_retry

logger = get_logger(__name__)


class GoogleSheetsClient:
    """Клиент для работы с Google Sheets."""

    def __init__(self):
        self.gc: gspread.Client | None = None
        self.workbook: gspread.Spreadsheet | None = None
        self._connect()

    def _connect(self) -> None:
        """Подключение к Google Sheets API."""
        try:
            credentials_info = json.loads(settings.GOOGLE_CREDENTIALS_JSON)
            credentials = Credentials.from_service_account_info(
                credentials_info,
                scopes=[
                    'https://www.googleapis.com/auth/spreadsheets',
                    'https://www.googleapis.com/auth/drive'
                ]
            )

            self.gc = gspread.authorize(credentials)
            self.workbook = self.gc.open_by_key(settings.GSHEETS_ID)

            logger.info("Successfully connected to Google Sheets",
                       sheets_id=settings.GSHEETS_ID)

        except Exception as e:
            logger.error("Failed to connect to Google Sheets", error=str(e))
            raise GoogleSheetsError(f"Ошибка подключения к Google Sheets: {e}")

    @google_sheets_retry
    def _get_worksheet(self, name: str) -> gspread.Worksheet:
        """Получение листа по имени."""
        try:
            return self.workbook.worksheet(name)
        except WorksheetNotFound:
            logger.warning(f"Worksheet '{name}' not found, creating...")
            return self._create_worksheet(name)
        except APIError as e:
            if e.response.status_code in [429, 500, 502, 503, 504]:
                raise RetryableError(f"Google Sheets API error: {e}")
            raise GoogleSheetsError(f"Ошибка доступа к листу {name}: {e}")

    def _create_worksheet(self, name: str) -> gspread.Worksheet:
        """Создание нового листа."""
        try:
            worksheet = self.workbook.add_worksheet(title=name, rows=1000, cols=20)
            logger.info(f"Created new worksheet: {name}")
            return worksheet
        except Exception as e:
            raise GoogleSheetsError(f"Ошибка создания листа {name}: {e}")

    @google_sheets_retry
    def _batch_update(self, worksheet: gspread.Worksheet, data: list[list[Any]]) -> None:
        """Batch обновление данных."""
        try:
            if not data:
                return

            # Определяем диапазон для обновления
            rows = len(data)
            cols = max(len(row) for row in data) if data else 0
            range_name = f"A1:{chr(65 + cols - 1)}{rows}"

            worksheet.batch_update([{
                'range': range_name,
                'values': data
            }])

            logger.debug(f"Batch updated {rows} rows in worksheet {worksheet.title}")

        except APIError as e:
            if e.response.status_code in [429, 500, 502, 503, 504]:
                raise RetryableError(f"Batch update failed: {e}")
            raise GoogleSheetsError(f"Ошибка batch обновления: {e}")

    # === Master_Blanks ===

    def initialize_master_blanks(self) -> None:
        """Инициализация справочника заготовок."""
        worksheet = self._get_worksheet("Master_Blanks")

        # Заголовки
        headers = [
            "blank_sku", "type", "size_mm", "color", "name_ua",
            "opening_stock", "min_stock", "par_stock", "active", "notes"
        ]

        # Данные для всех 20 SKU согласно ТЗ
        master_blanks_data = [
            # BONE заготовки
            ["BLK-BONE-25-GLD", "BONE", 25, "GLD", "кістка маленька", 200, 100, 300, True, ""],
            ["BLK-BONE-25-SIL", "BONE", 25, "SIL", "кістка маленька", 200, 100, 300, True, ""],
            ["BLK-BONE-30-GLD", "BONE", 30, "GLD", "кістка велика", 200, 100, 300, True, ""],
            ["BLK-BONE-30-SIL", "BONE", 30, "SIL", "кістка велика", 200, 100, 300, True, ""],

            # RING заготовки
            ["BLK-RING-25-GLD", "RING", 25, "GLD", "бублик 25мм", 200, 100, 300, True, ""],
            ["BLK-RING-25-SIL", "RING", 25, "SIL", "бублик 25мм", 200, 100, 300, True, ""],
            ["BLK-RING-30-GLD", "RING", 30, "GLD", "бублик 30мм", 200, 100, 300, True, ""],
            ["BLK-RING-30-SIL", "RING", 30, "SIL", "бублик 30мм", 200, 100, 300, True, ""],

            # ROUND заготовки
            ["BLK-ROUND-20-GLD", "ROUND", 20, "GLD", "круглий 20мм", 200, 100, 300, True, ""],
            ["BLK-ROUND-20-SIL", "ROUND", 20, "SIL", "круглий 20мм", 200, 100, 300, True, ""],
            ["BLK-ROUND-25-GLD", "ROUND", 25, "GLD", "круглий 25мм", 200, 100, 300, True, ""],
            ["BLK-ROUND-25-SIL", "ROUND", 25, "SIL", "круглий 25мм", 200, 100, 300, True, ""],
            ["BLK-ROUND-30-GLD", "ROUND", 30, "GLD", "круглий 30мм", 200, 100, 300, True, ""],
            ["BLK-ROUND-30-SIL", "ROUND", 30, "SIL", "круглий 30мм", 200, 100, 300, True, ""],

            # HEART заготовки
            ["BLK-HEART-25-GLD", "HEART", 25, "GLD", "серце", 200, 100, 300, True, ""],
            ["BLK-HEART-25-SIL", "HEART", 25, "SIL", "серце", 200, 100, 300, True, ""],

            # CLOUD заготовки
            ["BLK-CLOUD-25-GLD", "CLOUD", 25, "GLD", "хмарка", 200, 100, 300, True, ""],
            ["BLK-CLOUD-25-SIL", "CLOUD", 25, "SIL", "хмарка", 200, 100, 300, True, ""],

            # FLOWER заготовки
            ["BLK-FLOWER-25-GLD", "FLOWER", 25, "GLD", "квітка", 200, 100, 300, True, ""],
            ["BLK-FLOWER-25-SIL", "FLOWER", 25, "SIL", "квітка", 200, 100, 300, True, ""],
        ]

        data_to_update = [headers] + master_blanks_data
        self._batch_update(worksheet, data_to_update)

        logger.info("Initialized Master_Blanks with 20 SKUs")

    def get_master_blanks(self) -> list[MasterBlank]:
        """Получение справочника заготовок."""
        worksheet = self._get_worksheet("Master_Blanks")
        records = worksheet.get_all_records()

        blanks = []
        for record in records:
            blank = MasterBlank(
                blank_sku=record["blank_sku"],
                type=record["type"],
                size_mm=int(record["size_mm"]),
                color=record["color"],
                name_ua=record["name_ua"],
                opening_stock=int(record.get("opening_stock", 0)),
                min_stock=int(record.get("min_stock", 100)),
                par_stock=int(record.get("par_stock", 300)),
                active=bool(record.get("active", True)),
                notes=record.get("notes", "")
            )
            blanks.append(blank)

        logger.debug(f"Retrieved {len(blanks)} master blanks")
        return blanks

    # === Mapping ===

    def initialize_mapping(self) -> None:
        """Инициализация маппинга товаров."""
        worksheet = self._get_worksheet("Mapping")

        headers = [
            "product_name", "size_property", "metal_color", "blank_sku",
            "qty_per_unit", "active", "priority", "created_at"
        ]

        # Маппинг согласно ТЗ (украинские названия)
        mapping_data = [
            ["Адресник бублик", "25 мм", "золото", "BLK-RING-25-GLD", 1, True, 50, "2025-08-25T10:00:00"],
            ["Адресник бублик", "25 мм", "срібло", "BLK-RING-25-SIL", 1, True, 50, "2025-08-25T10:00:00"],
            ["Адресник бублик", "30 мм", "золото", "BLK-RING-30-GLD", 1, True, 50, "2025-08-25T10:00:00"],
            ["Адресник бублик", "30 мм", "срібло", "BLK-RING-30-SIL", 1, True, 50, "2025-08-25T10:00:00"],

            ["Адресник фігурний", "серце", "золото", "BLK-HEART-25-GLD", 1, True, 50, "2025-08-25T10:00:00"],
            ["Адресник фігурний", "серце", "срібло", "BLK-HEART-25-SIL", 1, True, 50, "2025-08-25T10:00:00"],
            ["Адресник фігурний", "квітка", "золото", "BLK-FLOWER-25-GLD", 1, True, 50, "2025-08-25T10:00:00"],
            ["Адресник фігурний", "квітка", "срібло", "BLK-FLOWER-25-SIL", 1, True, 50, "2025-08-25T10:00:00"],
            ["Адресник фігурний", "хмарка", "золото", "BLK-CLOUD-25-GLD", 1, True, 50, "2025-08-25T10:00:00"],
            ["Адресник фігурний", "хмарка", "срібло", "BLK-CLOUD-25-SIL", 1, True, 50, "2025-08-25T10:00:00"],

            ["Адресник кістка", "маленька", "золото", "BLK-BONE-25-GLD", 1, True, 50, "2025-08-25T10:00:00"],
            ["Адресник кістка", "маленька", "срібло", "BLK-BONE-25-SIL", 1, True, 50, "2025-08-25T10:00:00"],
            ["Адресник кістка", "велика", "золото", "BLK-BONE-30-GLD", 1, True, 50, "2025-08-25T10:00:00"],
            ["Адресник кістка", "велика", "срібло", "BLK-BONE-30-SIL", 1, True, 50, "2025-08-25T10:00:00"],

            ["Адресник", "20 мм", "золото", "BLK-ROUND-20-GLD", 1, True, 50, "2025-08-25T10:00:00"],
            ["Адресник", "20 мм", "срібло", "BLK-ROUND-20-SIL", 1, True, 50, "2025-08-25T10:00:00"],
            ["Адресник", "25 мм", "золото", "BLK-ROUND-25-GLD", 1, True, 50, "2025-08-25T10:00:00"],
            ["Адресник", "25 мм", "срібло", "BLK-ROUND-25-SIL", 1, True, 50, "2025-08-25T10:00:00"],
            ["Адресник", "30 мм", "золото", "BLK-ROUND-30-GLD", 1, True, 50, "2025-08-25T10:00:00"],
            ["Адресник", "30 мм", "срібло", "BLK-ROUND-30-SIL", 1, True, 50, "2025-08-25T10:00:00"],
        ]

        data_to_update = [headers] + mapping_data
        self._batch_update(worksheet, data_to_update)

        logger.info("Initialized Mapping with 20 rules")

    def get_product_mappings(self) -> list[ProductMapping]:
        """Получение правил маппинга."""
        worksheet = self._get_worksheet("Mapping")
        records = worksheet.get_all_records()

        mappings = []
        for record in records:
            mapping = ProductMapping(
                product_name=record["product_name"],
                size_property=record["size_property"],
                metal_color=record["metal_color"],
                blank_sku=record["blank_sku"],
                qty_per_unit=int(record.get("qty_per_unit", 1)),
                active=bool(record.get("active", True)),
                priority=int(record.get("priority", 50)),
                created_at=datetime.fromisoformat(record["created_at"])
            )
            mappings.append(mapping)

        # Сортировка по приоритету
        mappings.sort(key=lambda x: x.priority, reverse=True)

        logger.debug(f"Retrieved {len(mappings)} product mappings")
        return mappings

    # === Movements ===

    def add_movements(self, movements: list[Movement]) -> None:
        """Добавление нескольких движений товара (batch)."""
        if not movements:
            return

        worksheet = self._get_worksheet("Movements")

        # Проверяем заголовки
        if worksheet.row_count == 0 or not worksheet.row_values(1):
            headers = [
                "id", "datetime", "type", "source_type", "source_id",
                "blank_sku", "qty", "balance_after", "user", "note", "hash"
            ]
            worksheet.append_row(headers)

        # Подготавливаем данные для batch добавления
        rows_data = []
        for movement in movements:
            row_data = [
                str(movement.id),
                movement.timestamp.isoformat(),
                movement.type.value,
                movement.source_type.value,
                movement.source_id,
                movement.blank_sku,
                movement.qty,
                movement.balance_after,
                movement.user or "",
                movement.note or "",
                movement.hash
            ]
            rows_data.append(row_data)

        # Batch добавление всех строк за один запрос
        if rows_data:
            worksheet.append_rows(rows_data)

        logger.info(f"Added {len(movements)} movements")

    def add_movement(self, movement: Movement) -> None:
        """Добавление движения товара."""
        worksheet = self._get_worksheet("Movements")

        # Проверяем заголовки (добавляем если лист пустой)
        if worksheet.row_count == 0 or not worksheet.row_values(1):
            headers = [
                "id", "datetime", "type", "source_type", "source_id",
                "blank_sku", "qty", "balance_after", "user", "note", "hash"
            ]
            worksheet.append_row(headers)

        row_data = [
            str(movement.id),
            movement.timestamp.isoformat(),
            movement.type.value,
            movement.source_type.value,
            movement.source_id,
            movement.blank_sku,
            movement.qty,
            movement.balance_after,
            movement.user or "",
            movement.note or "",
            movement.hash
        ]

        worksheet.append_row(row_data)
        logger.info(f"Added movement: {movement.blank_sku} {movement.qty:+d}")

    def get_movements(self,
                     blank_sku: str | None = None,
                     limit: int | None = None) -> list[Movement]:
        """Получение движений товара."""
        worksheet = self._get_worksheet("Movements")
        records = worksheet.get_all_records()

        movements = []
        for record in records:
            if blank_sku and record["blank_sku"] != blank_sku:
                continue

            # Парсим timestamp и делаем его naive для совместимости
            timestamp = datetime.fromisoformat(record["datetime"])
            if timestamp.tzinfo is not None:
                timestamp = timestamp.replace(tzinfo=None)
                
            movement = Movement(
                id=record["id"],
                timestamp=timestamp,
                type=record["type"],
                source_type=record["source_type"],
                source_id=record["source_id"],
                blank_sku=record["blank_sku"],
                qty=int(record["qty"]),
                balance_after=int(record["balance_after"]),
                user=record.get("user"),
                note=record.get("note"),
                hash=record["hash"]
            )
            movements.append(movement)

        # Сортировка по времени (новые первыми)
        movements.sort(key=lambda x: x.timestamp, reverse=True)

        if limit:
            movements = movements[:limit]

        logger.debug(f"Retrieved {len(movements)} movements")
        return movements

    # === Current_Stock ===

    def update_current_stock(self, stocks: list[CurrentStock]) -> None:
        """Обновление текущих остатков - находит и обновляет существующие записи или создает новые."""
        worksheet = self._get_worksheet("Current_Stock")
        
        # Получаем все существующие записи
        existing_records = worksheet.get_all_records()
        existing_skus = {record.get("blank_sku"): i + 2 for i, record in enumerate(existing_records)}  # +2 для заголовка
        
        updates_to_make = []
        
        for stock in stocks:
            row_data = [
                stock.blank_sku,
                stock.on_hand,
                stock.reserved,
                stock.available,
                stock.last_receipt_date.isoformat() if stock.last_receipt_date else "",
                stock.last_order_date.isoformat() if stock.last_order_date else "",
                stock.avg_daily_usage,
                stock.days_of_stock or "",
                stock.last_updated.isoformat()
            ]
            
            if stock.blank_sku in existing_skus:
                # Обновляем существующую запись
                row_number = existing_skus[stock.blank_sku]
                range_name = f"A{row_number}:I{row_number}"
                updates_to_make.append({
                    'range': range_name,
                    'values': [row_data]
                })
                logger.debug(f"Updating existing stock record for {stock.blank_sku} at row {row_number}")
            else:
                # Добавляем новую запись в конец
                next_row = len(existing_records) + 2  # +2 для заголовка
                range_name = f"A{next_row}:I{next_row}"
                updates_to_make.append({
                    'range': range_name,
                    'values': [row_data]
                })
                # Обновляем индекс для следующих записей
                existing_skus[stock.blank_sku] = next_row
                existing_records.append({})  # Добавляем пустую запись для корректного подсчета
                logger.debug(f"Creating new stock record for {stock.blank_sku} at row {next_row}")
        
        if updates_to_make:
            worksheet.batch_update(updates_to_make)
            logger.debug(f"Batch updated {len(updates_to_make)} rows in worksheet Current_Stock")
            
        logger.info(f"Updated current stock for {len(stocks)} SKUs")

    # === Replenishment_Report ===

    def update_replenishment_report(self, recommendations: list[ReplenishmentRecommendation]) -> None:
        """Обновление отчета по закупкам."""
        worksheet = self._get_worksheet("Replenishment_Report")

        headers = [
            "blank_sku", "on_hand", "min_level", "reorder_point", "target_level",
            "need_order", "recommended_qty", "urgency", "estimated_stockout", "last_calculated"
        ]

        data_to_update = [headers]
        for rec in recommendations:
            row = [
                rec.blank_sku,
                rec.on_hand,
                rec.min_level,
                rec.reorder_point,
                rec.target_level,
                rec.need_order,
                rec.recommended_qty,
                rec.urgency.value,
                rec.estimated_stockout.isoformat() if rec.estimated_stockout else "",
                rec.last_calculated.isoformat()
            ]
            data_to_update.append(row)

        self._batch_update(worksheet, data_to_update)
        logger.info(f"Updated replenishment report with {len(recommendations)} recommendations")

    # === Utility methods ===

    def create_all_worksheets(self) -> None:
        """Создание всех необходимых листов."""
        required_sheets = [
            "Config", "Master_Blanks", "Mapping", "Movements",
            "Current_Stock", "Replenishment_Report", "Unmapped_Items",
            "Audit_Log", "Analytics_Dashboard"
        ]

        for sheet_name in required_sheets:
            try:
                self._get_worksheet(sheet_name)
                logger.info(f"Worksheet '{sheet_name}' ready")
            except Exception as e:
                logger.error(f"Failed to create worksheet '{sheet_name}': {e}")

        logger.info("All worksheets initialized")

    # === Дополнительные методы для StockService ===

    @google_sheets_retry
    def get_current_stock(self, blank_sku: str) -> CurrentStock | None:
        """Получение текущего остатка по SKU."""
        try:
            worksheet = self._get_worksheet("Current_Stock")
            records = worksheet.get_all_records()

            for record in records:
                if record.get("blank_sku") == blank_sku:
                    return CurrentStock(
                        blank_sku=record["blank_sku"],
                        on_hand=int(record.get("on_hand", 0)),
                        reserved=int(record.get("reserved", 0)),
                        available=int(record.get("available", 0)),
                        last_receipt_date=date.fromisoformat(record["last_receipt_date"]) if record.get("last_receipt_date") else None,
                        last_order_date=date.fromisoformat(record["last_order_date"]) if record.get("last_order_date") else None,
                        avg_daily_usage=float(record.get("avg_daily_usage", 0.0)),
                        days_of_stock=int(record["days_of_stock"]) if record.get("days_of_stock") else None,
                        last_updated=datetime.fromisoformat(record.get("last_updated", datetime.now().isoformat()))
                    )

            return None

        except Exception as e:
            logger.error(f"Failed to get current stock for {blank_sku}", error=str(e))
            return None

    @google_sheets_retry
    def get_all_current_stock(self) -> list[CurrentStock]:
        """Получение всех текущих остатков."""
        try:
            worksheet = self._get_worksheet("Current_Stock")
            records = worksheet.get_all_records()

            stocks = []
            for record in records:
                stock = CurrentStock(
                    blank_sku=record["blank_sku"],
                    on_hand=int(record.get("on_hand", 0)),
                    reserved=int(record.get("reserved", 0)),
                    available=int(record.get("available", 0)),
                    last_receipt_date=date.fromisoformat(record["last_receipt_date"]) if record.get("last_receipt_date") else None,
                    last_order_date=date.fromisoformat(record["last_order_date"]) if record.get("last_order_date") else None,
                    avg_daily_usage=float(record.get("avg_daily_usage", 0.0)),
                    days_of_stock=int(record["days_of_stock"]) if record.get("days_of_stock") else None,
                    last_updated=datetime.fromisoformat(record.get("last_updated", datetime.now().isoformat()))
                )
                stocks.append(stock)

            return stocks

        except Exception as e:
            logger.error("Failed to get all current stock", error=str(e))
            return []

    @google_sheets_retry
    def movement_exists(self, movement_hash: str) -> bool:
        """Проверка существования движения по хешу."""
        try:
            worksheet = self._get_worksheet("Movements")
            records = worksheet.get_all_records()

            for record in records:
                if record.get("hash") == movement_hash:
                    return True

            return False

        except Exception as e:
            logger.error(f"Failed to check movement existence for hash {movement_hash}", error=str(e))
            return False

    @google_sheets_retry
    def add_unmapped_items(self, unmapped_items: list[UnmappedItem]) -> None:
        """Добавление unmapped позиций."""
        if not unmapped_items:
            return

        try:
            worksheet = self._get_worksheet("Unmapped_Items")

            # Проверяем заголовки
            if worksheet.row_count == 0 or not worksheet.row_values(1):
                headers = [
                    "datetime", "order_id", "line_id", "product_name",
                    "properties", "suggested_sku", "error_type", "resolution"
                ]
                worksheet.append_row(headers)

            # Добавляем записи
            for item in unmapped_items:
                row_data = [
                    item.timestamp.isoformat(),
                    item.order_id,
                    item.line_id,
                    item.product_name,
                    json.dumps(item.properties),
                    item.suggested_sku or "",
                    item.error_type,
                    item.resolution
                ]
                worksheet.append_row(row_data)

            logger.info(f"Added {len(unmapped_items)} unmapped items")

        except Exception as e:
            logger.error("Failed to add unmapped items", error=str(e))
            raise GoogleSheetsError(f"Failed to add unmapped items: {e}")


# Создаем alias для обратной совместимости
SheetsClient = GoogleSheetsClient

# Глобальный экземпляр клиента
_sheets_client: SheetsClient | None = None


def get_sheets_client() -> SheetsClient:
    """Получение глобального экземпляра Sheets клиента."""
    global _sheets_client

    if _sheets_client is None:
        _sheets_client = SheetsClient()

    return _sheets_client
