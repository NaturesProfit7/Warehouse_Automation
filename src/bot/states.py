"""Состояния для диалогов Telegram бота."""

from aiogram.fsm.state import State, StatesGroup


class ReceiptStates(StatesGroup):
    """Состояния для добавления прихода."""
    
    waiting_for_type = State()          # Ожидание выбора типа заготовки
    waiting_for_size = State()          # Ожидание выбора размера/свойства
    waiting_for_color = State()         # Ожидание выбора цвета
    waiting_for_quantity = State()      # Ожидание ввода количества
    waiting_for_confirmation = State()  # Ожидание подтверждения (для больших партий)


class CorrectionStates(StatesGroup):
    """Состояния для корректировки остатков."""
    
    waiting_for_sku = State()           # Ожидание выбора SKU
    waiting_for_quantity = State()      # Ожидание ввода количества
    waiting_for_reason = State()        # Ожидание причины корректировки
    waiting_for_confirmation = State()  # Ожидание подтверждения


class ReportStates(StatesGroup):
    """Состояния для генерации отчетов."""
    
    waiting_for_report_type = State()   # Ожидание выбора типа отчета
    waiting_for_filters = State()       # Ожидание настройки фильтров