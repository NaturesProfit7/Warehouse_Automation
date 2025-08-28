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

# 3. Деплой одной командой
./deploy.sh deploy

# 4. Проверка статуса
curl http://localhost:8000/health
```

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

```
┌─────────────┐    ┌──────────────┐    ┌─────────────────┐
│   KeyCRM    │───▶│   Webhook    │───▶│  Google Sheets  │
│  (заказы)   │    │ (списание)   │    │  (движения)     │
└─────────────┘    └──────────────┘    └─────────────────┘
                            │                    ▲
                            ▼                    │
┌─────────────┐    ┌──────────────┐              │
│ Telegram    │◀───│  Scheduler   │──────────────┘
│ (уведомления)│    │ (расчеты)    │
└─────────────┘    └──────────────┘
       ▲                    
       │            ┌──────────────┐
       └────────────│ Telegram Bot │
                    │ (приходы)    │
                    └──────────────┘
```

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
- **Health Check**: `http://your-server:8000/health`
- **Detailed Status**: `http://your-server:8000/health` (JSON response)
- **Telegram monitoring**: `/health` команда в боте

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

1. **Проверьте health status**: `curl http://localhost:8000/health`
2. **Посмотрите логи**: `./deploy.sh logs`  
3. **Telegram мониторинг**: отправьте `/health` боту
4. **Debug mode**: установите `DEBUG=true` в `.env`

---

**🎯 Система готова к production использованию!**

Разработано с ❤️ для эффективного управления складскими запасами.