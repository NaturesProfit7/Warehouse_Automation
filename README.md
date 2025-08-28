# 🏪 Warehouse Automation System

MVP система автоматического планирования закупок металлических заготовок для адресников с интеграцией KeyCRM и Google Sheets.

## ✨ Возможности

- ✅ **Автоматический расчет потребности** в заготовках с учетом брака и сроков поставки
- ✅ **Ежедневные уведомления** о необходимости закупки через Telegram
- ✅ **Простой учет приходов** через Telegram-бот с интуитивным интерфейсом  
- ✅ **Полная прозрачность остатков** в Google Sheets
- ✅ **Webhook интеграция** с KeyCRM для автоматического списания
- ✅ **Умная фильтрация товаров** - обрабатываются только адресники
- ✅ **Система мониторинга** с health checks и alerts
- ✅ **Docker контейнеризация** для простого деплоя

## 🚀 Быстрый старт

### Production деплой (Docker)

```bash
# 1. Клонирование
git clone https://github.com/NaturesProfit7/Warehouse_Automation.git
cd Warehouse_Automation

# 2. Настройка конфигурации
cp .env.template .env
nano .env  # заполните реальными данными

# 3. Деплой с новыми исправлениями
docker compose down  # остановка старых контейнеров
docker compose up -d --build

# 4. Проверка статуса (новые порты!)
curl http://localhost:9001/health  # Telegram bot
curl http://localhost:9000/health  # Webhook server
```

> **⚠️ Важно:** В новой версии изменились порты:
> - Telegram bot health check: **9001** (было 8000)
> - KeyCRM webhook server: **9000** (новый порт)

### Локальная разработка

```bash
# Установка зависимостей
python -m venv venv
source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt

# Запуск системы
python main_with_scheduler.py
```

## 🏗️ Архитектура

### Новая microservices архитектура:

```
┌─────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   KeyCRM    │───▶│ Webhook Server   │───▶│  Google Sheets  │
│  (заказы)   │    │   (Port 9000)    │    │   (движения)    │
└─────────────┘    └──────────────────┘    └─────────────────┘
                                                     ▲
┌──────────────────┐                                 │
│ Telegram Bot +   │◀────────────────────────────────┘
│ Scheduler        │      
│ (Port 9001)      │      ┌──────────────────┐
└─────────┬────────┘◀─────│ Nginx Reverse    │
          │                │ Proxy (443/80)   │
          ▼                └──────────────────┘
┌─────────────────┐                 ▲
│ Google Sheets   │                 │
│ (расчеты/отчеты)│       ┌─────────┴─────────┐
└─────────────────┘       │   External API    │
                          │   (KeyCRM Hook)   │
                          └───────────────────┘
```

### Разделение сервисов:
- **telegram-bot**: Telegram polling + планировщик + health check (:9001)
- **webhook-server**: KeyCRM webhooks + FastAPI (:9000)
- **nginx**: Reverse proxy + SSL termination (:443)

## ⚙️ Конфигурация

Основные переменные окружения:

| Переменная | Описание | Обязательная |
|------------|----------|--------------|
| `KEYCRM_API_TOKEN` | Токен KeyCRM API | Да |
| `GSHEETS_ID` | ID Google Sheets книги | Да |
| `GOOGLE_CREDENTIALS_JSON` | Service Account credentials | Да |
| `TELEGRAM_BOT_TOKEN` | Токен Telegram бота | Да |
| `TELEGRAM_ALLOWED_USERS` | Список разрешенных user_id | Да |

Полный список см. в [.env.template](.env.template)

## 📁 Структура проекта

```
├── main_with_scheduler.py    # 🚀 Точка входа приложения
├── requirements.txt          # 📦 Зависимости
├── Dockerfile               # 🐳 Контейнер
├── docker-compose.yml       # 🎼 Оркестрация
├── deploy.sh               # 🛠️ Скрипт деплоя
├── .env.template           # ⚙️ Шаблон конфигурации
├── CLAUDE.md               # 📋 Правила проекта
├── src/                    # 📚 Исходный код
│   ├── bot/               # 🤖 Telegram бот
│   ├── core/              # 💎 Базовые модели
│   ├── integrations/      # 🔗 Внешние API
│   ├── services/          # 🏗️ Бизнес-сервисы  
│   ├── scheduler/         # ⏰ Планировщик
│   ├── webhook/           # 🔗 Webhook handlers
│   └── utils/             # 🛠️ Утилиты
├── tests/                  # 🧪 Тесты (54 файла)
├── docs/                   # 📖 Документация
│   ├── DEPLOYMENT.md       # 📋 Инструкция деплоя
│   ├── TZ.md              # 📝 Техническое задание
│   └── ...                # 📚 Остальная документация
└── dev_tools/             # 🔧 Инструменты разработки
    ├── debug_*.py         # 🐛 Отладочные скрипты
    └── test_*.py          # 🧪 Тестовые скрипты
```

## 🚢 Деплой

### Автоматический деплой (рекомендуется)
```bash
./deploy.sh deploy    # Полный деплой
./deploy.sh status    # Проверка статуса  
./deploy.sh logs      # Просмотр логов
./deploy.sh restart   # Перезапуск
```

### Мониторинг
- **Telegram Bot Health**: `http://your-server:9001/health`
- **Webhook Server Health**: `http://your-server:9000/health`
- **External Health Check**: `https://warehouse.timosh-design.com/health`
- **Telegram monitoring**: `/health` команда в боте

### Новые возможности мониторинга:
- Раздельный мониторинг сервисов
- Улучшенные health checks с таймаутами
- Автоматическое восстановление при сбоях
- Детальная диагностика компонентов

## 🤖 Telegram бот

### Команды
- `/start` - главное меню
- `/receipt` - добавить приход заготовок
- `/report` - отчет по остаткам  
- `/health` - статус системы с интерактивными кнопками
- `/help` - справка

### Функции мониторинга
Бот предоставляет real-time мониторинг:
- 📊 Статус всех компонентов системы
- ⏰ Состояние планировщика задач
- 📈 Uptime и метрики производительности  
- 🔔 Настройка уведомлений

## 📊 Система мониторинга

- **5 компонентов** отслеживается
- **4 фоновые задачи** по расписанию
- **Критичные уведомления** при проблемах
- **Daily summary** отчёты
- **Health trends** анализ

## 🔒 Безопасность

- ✅ HMAC подпись webhooks
- ✅ Whitelist Telegram пользователей  
- ✅ Rate limiting на endpoints
- ✅ Секреты в переменных окружения
- ✅ Non-root пользователь в Docker
- ✅ SSL/TLS поддержка

## 📚 Документация

- 📋 [Инструкция деплоя](docs/DEPLOYMENT.md)  
- 🎯 [Production checklist](docs/PRODUCTION_CHECKLIST.md)
- 🔄 [GitHub Actions setup](docs/GITHUB_ACTIONS_SETUP.md)
- 📊 [Мониторинг системы](docs/README_MONITORING.md)
- 🧪 [Инструкции тестирования](docs/TESTING_INSTRUCTIONS.md)
- 📝 [Техническое задание](docs/TZ.md)

## 🆘 Поддержка

При возникновении проблем:

1. **Проверьте health status**: 
   ```bash
   curl http://localhost:9001/health  # Telegram bot
   curl http://localhost:9000/health  # Webhook server
   ```

2. **Посмотрите логи раздельно**: 
   ```bash
   docker compose logs -f telegram-bot
   docker compose logs -f webhook-server
   ```

3. **Telegram мониторинг**: отправьте `/health` боту

4. **Debug mode**: установите `DEBUG=true` в `.env`

5. **Решение частых проблем**:
   ```bash
   # Конфликт Telegram bot instances
   docker compose restart telegram-bot
   
   # Полный перезапуск с очисткой
   docker compose down && docker compose up -d --build
   ```

---

**🎯 Система готова к production использованию!**

Разработано с ❤️ для эффективного управления складскими запасами.