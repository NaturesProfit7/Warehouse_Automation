"""Тесты для Google Sheets интеграции."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from uuid import uuid4

from src.integrations.sheets import GoogleSheetsClient
from src.core.models import MasterBlank, Movement, MovementType, MovementSourceType, BlankType, BlankColor
from src.core.exceptions import GoogleSheetsError, RetryableError


@pytest.fixture
def mock_gspread():
    """Mock для gspread клиента."""
    with patch('src.integrations.sheets.gspread') as mock:
        yield mock


@pytest.fixture
def mock_credentials():
    """Mock для Google credentials."""
    with patch('src.integrations.sheets.Credentials') as mock:
        yield mock


@pytest.fixture
def mock_worksheet():
    """Mock для Google Sheets worksheet."""
    worksheet = Mock()
    worksheet.title = "Test_Sheet"
    worksheet.row_count = 10
    worksheet.append_row = Mock()
    worksheet.batch_update = Mock()
    worksheet.get_all_records = Mock(return_value=[])
    worksheet.row_values = Mock(return_value=["header1", "header2"])
    return worksheet


@pytest.fixture
def mock_workbook(mock_worksheet):
    """Mock для Google Sheets workbook."""
    workbook = Mock()
    workbook.worksheet = Mock(return_value=mock_worksheet)
    workbook.add_worksheet = Mock(return_value=mock_worksheet)
    return workbook


@pytest.fixture
def sheets_client(mock_gspread, mock_credentials, mock_workbook):
    """Google Sheets клиент с моками."""
    mock_gspread.authorize.return_value.open_by_key.return_value = mock_workbook
    
    with patch('src.integrations.sheets.settings') as mock_settings:
        mock_settings.GOOGLE_CREDENTIALS_JSON = '{"type": "service_account"}'
        mock_settings.GSHEETS_ID = "test_sheet_id"
        
        client = GoogleSheetsClient()
        return client


class TestGoogleSheetsClient:
    """Тесты для GoogleSheetsClient."""
    
    def test_connection_success(self, mock_gspread, mock_credentials, mock_workbook):
        """Тест успешного подключения."""
        mock_gspread.authorize.return_value.open_by_key.return_value = mock_workbook
        
        with patch('src.integrations.sheets.settings') as mock_settings:
            mock_settings.GOOGLE_CREDENTIALS_JSON = '{"type": "service_account"}'
            mock_settings.GSHEETS_ID = "test_id"
            
            client = GoogleSheetsClient()
            assert client.gc is not None
            assert client.workbook is not None

    def test_connection_failure(self, mock_gspread, mock_credentials):
        """Тест неудачного подключения."""
        mock_gspread.authorize.side_effect = Exception("Connection failed")
        
        with patch('src.integrations.sheets.settings') as mock_settings:
            mock_settings.GOOGLE_CREDENTIALS_JSON = '{"type": "service_account"}'
            mock_settings.GSHEETS_ID = "test_id"
            
            with pytest.raises(GoogleSheetsError):
                GoogleSheetsClient()

    def test_get_worksheet_existing(self, sheets_client, mock_workbook, mock_worksheet):
        """Тест получения существующего листа."""
        mock_workbook.worksheet.return_value = mock_worksheet
        
        worksheet = sheets_client._get_worksheet("TestSheet")
        assert worksheet == mock_worksheet
        mock_workbook.worksheet.assert_called_once_with("TestSheet")

    def test_get_worksheet_not_found_creates_new(self, sheets_client, mock_workbook, mock_worksheet):
        """Тест создания нового листа если не найден."""
        from gspread.exceptions import WorksheetNotFound
        
        mock_workbook.worksheet.side_effect = WorksheetNotFound("Not found")
        mock_workbook.add_worksheet.return_value = mock_worksheet
        
        worksheet = sheets_client._get_worksheet("NewSheet")
        assert worksheet == mock_worksheet
        mock_workbook.add_worksheet.assert_called_once()

    def test_batch_update_success(self, sheets_client, mock_worksheet):
        """Тест успешного batch обновления."""
        data = [["Header1", "Header2"], ["Value1", "Value2"]]
        
        sheets_client._batch_update(mock_worksheet, data)
        mock_worksheet.batch_update.assert_called_once()

    def test_batch_update_empty_data(self, sheets_client, mock_worksheet):
        """Тест batch обновления с пустыми данными."""
        sheets_client._batch_update(mock_worksheet, [])
        mock_worksheet.batch_update.assert_not_called()

    def test_initialize_master_blanks(self, sheets_client, mock_worksheet):
        """Тест инициализации справочника заготовок."""
        sheets_client.initialize_master_blanks()
        
        # Проверяем что batch_update был вызван
        mock_worksheet.batch_update.assert_called_once()
        
        # Проверяем структуру данных
        call_args = mock_worksheet.batch_update.call_args
        update_data = call_args[0][0][0]['values']
        
        # Первая строка - заголовки
        headers = update_data[0]
        assert "blank_sku" in headers
        assert "type" in headers
        assert "name_ua" in headers
        
        # Проверяем что есть все 20 SKU
        data_rows = update_data[1:]  # Все кроме заголовков
        assert len(data_rows) == 20
        
        # Проверяем несколько конкретных SKU
        skus = [row[0] for row in data_rows]
        assert "BLK-BONE-25-GLD" in skus
        assert "BLK-HEART-25-SIL" in skus
        assert "BLK-FLOWER-25-GLD" in skus

    def test_get_master_blanks(self, sheets_client, mock_workbook, mock_worksheet):
        """Тест получения справочника заготовок."""
        mock_records = [
            {
                "blank_sku": "BLK-BONE-25-GLD",
                "type": "BONE",
                "size_mm": 25,
                "color": "GLD",
                "name_ua": "кістка маленька",
                "opening_stock": 200,
                "min_stock": 100,
                "par_stock": 300,
                "active": True,
                "notes": ""
            }
        ]
        
        mock_worksheet.get_all_records.return_value = mock_records
        mock_workbook.worksheet.return_value = mock_worksheet
        
        blanks = sheets_client.get_master_blanks()
        
        assert len(blanks) == 1
        blank = blanks[0]
        assert isinstance(blank, MasterBlank)
        assert blank.blank_sku == "BLK-BONE-25-GLD"
        assert blank.type == BlankType.BONE
        assert blank.color == BlankColor.GOLD

    def test_add_movement(self, sheets_client, mock_worksheet):
        """Тест добавления движения."""
        movement = Movement(
            id=uuid4(),
            type=MovementType.RECEIPT,
            source_type=MovementSourceType.TELEGRAM,
            source_id="test_source",
            blank_sku="BLK-BONE-25-GLD",
            qty=100,
            balance_after=300,
            hash="test_hash"
        )
        
        # Mock пустого листа
        mock_worksheet.row_count = 0
        mock_worksheet.row_values.return_value = []
        
        sheets_client.add_movement(movement)
        
        # Проверяем что были добавлены заголовки и данные
        assert mock_worksheet.append_row.call_count == 2

    def test_initialize_mapping(self, sheets_client, mock_worksheet):
        """Тест инициализации маппинга."""
        sheets_client.initialize_mapping()
        
        mock_worksheet.batch_update.assert_called_once()
        
        # Проверяем структуру данных
        call_args = mock_worksheet.batch_update.call_args
        update_data = call_args[0][0][0]['values']
        
        # Первая строка - заголовки
        headers = update_data[0]
        assert "product_name" in headers
        assert "blank_sku" in headers
        assert "metal_color" in headers
        
        # Проверяем что есть все 20 правил маппинга
        data_rows = update_data[1:]
        assert len(data_rows) == 20

    def test_create_all_worksheets(self, sheets_client, mock_workbook, mock_worksheet):
        """Тест создания всех листов."""
        sheets_client.create_all_worksheets()
        
        # Проверяем что worksheet был вызван для каждого обязательного листа
        expected_sheets = [
            "Config", "Master_Blanks", "Mapping", "Movements",
            "Current_Stock", "Replenishment_Report", "Unmapped_Items",
            "Audit_Log", "Analytics_Dashboard"
        ]
        
        assert mock_workbook.worksheet.call_count == len(expected_sheets)


class TestRetryLogic:
    """Тесты retry логики."""
    
    def test_retry_on_api_error(self, sheets_client, mock_worksheet):
        """Тест повторных попыток при API ошибках."""
        from gspread.exceptions import APIError
        from requests import Response
        
        # Создаем mock ответа с кодом 429 (rate limit)
        response = Mock(spec=Response)
        response.status_code = 429
        
        api_error = APIError(response)
        
        # Настраиваем mock чтобы первый раз выдавал ошибку, второй раз работал
        mock_worksheet.batch_update.side_effect = [api_error, None]
        
        # Должно пройти после retry
        with patch('time.sleep'):  # Убираем реальные задержки в тестах
            sheets_client._batch_update(mock_worksheet, [["test"]])
        
        # Проверяем что было 2 попытки
        assert mock_worksheet.batch_update.call_count == 2

    def test_retry_exhaustion(self, sheets_client, mock_worksheet):
        """Тест исчерпания попыток retry."""
        from gspread.exceptions import APIError
        from requests import Response
        
        response = Mock(spec=Response)
        response.status_code = 500
        
        api_error = APIError(response)
        mock_worksheet.batch_update.side_effect = api_error
        
        # Должно выбросить исключение после исчерпания попыток
        with patch('time.sleep'):
            with pytest.raises(APIError):
                sheets_client._batch_update(mock_worksheet, [["test"]])