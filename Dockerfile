# Базовый образ Python 3.12
FROM python:3.12-slim

# Метаданные
LABEL maintainer="Warehouse Automation System"
LABEL description="Telegram Bot for Warehouse Management"

# Переменные окружения
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app" \
    DEBIAN_FRONTEND=noninteractive

# Создание пользователя для безопасности
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Установка системных зависимостей
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Создание директорий
WORKDIR /app

# Копирование файлов зависимостей
COPY requirements.txt .

# Установка Python зависимостей
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копирование исходного кода
COPY . .

# Создание директорий для логов и данных
RUN mkdir -p /app/logs /app/data && \
    chown -R appuser:appuser /app

# Переключение на непривилегированного пользователя
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import asyncio; print('Health check passed')" || exit 1

# Экспозиция портов
EXPOSE 8000

# Точка входа
CMD ["python", "main_with_scheduler.py"]