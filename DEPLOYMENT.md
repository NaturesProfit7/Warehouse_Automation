# 🚀 Инструкция по развертыванию системы автоматизации склада

## 📋 Предварительные требования

### Системные требования
- Python 3.11+ 
- Git
- Доступ к интернету для установки пакетов

### Необходимые сервисы
- Google Sheets API доступ
- KeyCRM API токен
- Telegram Bot токен

## 🔧 Установка и настройка

### 1. Клонирование репозитория

```bash
git clone https://github.com/NaturesProfit7/Warehouse_Automation.git
cd Warehouse_Automation
```

### 2. Создание виртуального окружения

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# или
venv\Scripts\activate     # Windows
```

### 3. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 4. Быстрый тест системы

```bash
python3 scripts/test_system.py
```

Этот скрипт проверит:
- ✅ Структуру проекта
- ✅ Базовую функциональность
- ✅ Синтаксис всех файлов
- ✅ Импорты модулей

## ⚙️ Настройка конфигурации

### 1. Создание .env файла

Скопируйте `.env.example` в `.env`:

```bash
cp .env.example .env
```

### 2. Заполнение переменных окружения

```env
# KeyCRM Integration
KEYCRM_API_URL=https://api.keycrm.app
KEYCRM_API_TOKEN=your_keycrm_token_here
KEYCRM_WEBHOOK_SECRET=your_webhook_secret

# Google Sheets
GSHEETS_ID=your_google_sheet_id
GOOGLE_CREDENTIALS_JSON={"type":"service_account",...}

# Telegram Bot
TELEGRAM_BOT_TOKEN=123:ABC-your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
TELEGRAM_ADMIN_USERS=user_id_1,user_id_2

# Stock Management Settings
LEAD_TIME_DAYS=14
SCRAP_PCT=0.05
TARGET_COVER_DAYS=30
```

## 🔑 Получение токенов и доступов

### Google Sheets API

1. Перейдите в [Google Cloud Console](https://console.cloud.google.com/)
2. Создайте новый проект или выберите существующий
3. Включите Google Sheets API
4. Создайте Service Account
5. Скачайте JSON-ключ
6. Вставьте содержимое JSON в `GOOGLE_CREDENTIALS_JSON`
7. Поделитесь таблицей с email из service account

### KeyCRM API

1. Войдите в административную панель KeyCRM
2. Перейдите в раздел API
3. Создайте новый API токен
4. Настройте webhook на ваш сервер: `https://yourdomain.com/webhook/keycrm`

### Telegram Bot

1. Напишите [@BotFather](https://t.me/botfather)
2. Создайте нового бота командой `/newbot`
3. Получите токен бота
4. Узнайте ваш chat_id (можно через [@userinfobot](https://t.me/userinfobot))

## 🏃‍♂️ Запуск системы

### Режим разработки

```bash
# Запуск компонентов по отдельности

# 1. Webhook сервер (FastAPI)
uvicorn src.webhook.app:app --host 0.0.0.0 --port 8000 --reload

# 2. Telegram бот
python3 -m src.bot

# 3. Планировщик задач
python3 -m src.scheduler.runner
```

### Продакшн режим

```bash
# Используйте Docker Compose
docker-compose up -d
```

### Проверка работы

```bash
# Проверка webhook
curl -X GET http://localhost:8000/health

# Проверка готовности
curl -X GET http://localhost:8000/ready
```

## 🧪 Тестирование

### Запуск всех тестов

```bash
# Базовые тесты (без внешних зависимостей)
pytest tests/test_basic.py -v

# Все unit тесты  
pytest tests/ -v

# Комплексный тест системы
python3 scripts/test_system.py
```

### Тестирование компонентов

```bash
# Тест конфигурации
python3 -c "from src.config import settings; print('Config OK')"

# Тест Telegram бота (эхо)
python3 -c "from src.bot import create_bot; print('Bot OK')"

# Тест калькулятора остатков
python3 -c "from src.core.calculations import get_stock_calculator; print('Calculator OK')"
```

## 🔧 Настройка Google Sheets

### Структура листов

Создайте следующие листы в Google Sheets:

1. **CurrentStock** - текущие остатки
   - Колонки: `blank_sku`, `on_hand`, `reserved`, `available`, `avg_daily_usage`, `last_updated`

2. **MasterBlanks** - справочник заготовок  
   - Колонки: `blank_sku`, `type`, `size_mm`, `color`, `name_ua`, `min_stock`, `par_stock`, `active`

3. **Movements** - движения товаров
   - Колонки: `id`, `blank_sku`, `type`, `source_type`, `qty`, `balance_after`, `order_id`, `user`, `note`, `timestamp`

4. **ProductMappings** - маппинг товаров KeyCRM → SKU
   - Колонки: `product_name`, `size_property`, `metal_color`, `blank_sku`, `qty_per_unit`, `active`, `priority`

5. **UnmappedItems** - немапленые товары
   - Колонки: `order_id`, `product_name`, `quantity`, `properties`, `created_at`

### Пример данных

**MasterBlanks:**
```
blank_sku          | type | size_mm | color | name_ua            | min_stock | par_stock | active
BLK-RING-25-GLD   | RING | 25      | GLD   | бублик 25мм золото | 100       | 300       | TRUE
BLK-RING-25-SIL   | RING | 25      | SIL   | бублик 25мм срібло | 100       | 300       | TRUE
```

**ProductMappings:**
```
product_name      | size_property | metal_color | blank_sku       | qty_per_unit | active | priority
Адресник бублик   | 25 мм         | золото      | BLK-RING-25-GLD | 1            | TRUE   | 50
Адресник бублик   | 25 мм         | срібло      | BLK-RING-25-SIL | 1            | TRUE   | 50
```

## 🚀 Развертывание в продакшене

### Вариант 1: VPS с systemd

1. Создайте systemd сервисы:

```bash
# /etc/systemd/system/warehouse-webhook.service
[Unit]
Description=Warehouse Webhook Service
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/warehouse_automation
Environment=PATH=/opt/warehouse_automation/venv/bin
ExecStart=/opt/warehouse_automation/venv/bin/uvicorn src.webhook.app:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

2. Включите и запустите сервисы:

```bash
sudo systemctl daemon-reload
sudo systemctl enable warehouse-webhook
sudo systemctl start warehouse-webhook
```

### Вариант 2: Docker

```bash
# Сборка образа
docker build -t warehouse-automation .

# Запуск с docker-compose
docker-compose up -d
```

### Настройка веб-сервера (nginx)

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location /webhook/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /health {
        proxy_pass http://127.0.0.1:8000;
    }
}
```

## 📊 Мониторинг и логи

### Просмотр логов

```bash
# Логи webhook сервера
tail -f logs/webhook.log

# Логи Telegram бота  
tail -f logs/bot.log

# Логи планировщика
tail -f logs/scheduler.log

# Системные логи
sudo journalctl -u warehouse-webhook -f
```

### Метрики и здоровье системы

```bash
# Проверка статуса компонентов
curl http://localhost:8000/health

# Проверка готовности
curl http://localhost:8000/ready

# Статус systemd сервисов
sudo systemctl status warehouse-*
```

## 🐛 Решение проблем

### Частые проблемы

**1. Ошибка импорта модулей**
```bash
# Убедитесь что PYTHONPATH настроен
export PYTHONPATH="${PYTHONPATH}:/path/to/warehouse_automation/src"
```

**2. Ошибка доступа к Google Sheets**
```bash
# Проверьте права service account
# Убедитесь что таблица расшарена для service account email
```

**3. Telegram бот не отвечает**
```bash
# Проверьте токен бота
curl https://api.telegram.org/bot<TOKEN>/getMe

# Проверьте webhook URL
curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo
```

**4. KeyCRM webhook не работает**
```bash  
# Проверьте HMAC подпись
# Убедитесь что URL доступен снаружи
# Проверьте логи webhook сервера
```

### Отладка

```bash
# Включение подробного логирования
export LOG_LEVEL=DEBUG

# Запуск в режиме отладки
python3 -m debugpy --listen 5678 --wait-for-client -m src.webhook.app
```

## 🔒 Безопасность

### Рекомендации

1. **Используйте HTTPS** для всех webhook endpoints
2. **Ограничьте доступ** к серверу по IP
3. **Регулярно обновляйте** токены и секреты  
4. **Мониторьте логи** на подозрительную активность
5. **Делайте бэкапы** конфигурации и данных

### Файрвол

```bash
# Открыть только необходимые порты
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP  
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
```

## 📈 Масштабирование

### Горизонтальное масштабирование

- Запустите несколько экземпляров webhook сервера за load balancer
- Используйте Redis для координации между процессами
- Реплицируйте базу данных для чтения

### Производительность

- Настройте connection pooling для внешних API
- Используйте кеширование для часто запрашиваемых данных
- Оптимизируйте запросы к Google Sheets API

## ✅ Чек-лист развертывания

- [ ] Система протестирована с помощью `scripts/test_system.py`
- [ ] Все переменные окружения настроены
- [ ] Google Sheets API доступ настроен
- [ ] Telegram бот создан и токен получен
- [ ] KeyCRM API токен получен и webhook настроен
- [ ] Структура Google Sheets создана
- [ ] SSL сертификат установлен (для продакшена)
- [ ] Мониторинг и логирование настроено
- [ ] Бэкапы настроены
- [ ] Firewall настроен

## 🆘 Поддержка

При возникновении проблем:

1. Проверьте логи системы
2. Запустите диагностический скрипт `python3 scripts/test_system.py`
3. Изучите документацию в `docs/`
4. Создайте issue в GitHub репозитории

---

🎉 **Поздравляем! Система автоматизации склада готова к работе!**