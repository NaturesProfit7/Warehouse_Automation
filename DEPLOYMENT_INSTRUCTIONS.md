# 🚀 Инструкция по деплою Warehouse Automation System

## 📋 Обзор системы

**Система состоит из 2 независимых сервисов:**

### 🤖 Telegram Bot Service (порт 9001)
- **Функции:** Telegram бот + планировщик уведомлений
- **Запуск:** `python main_with_scheduler.py`
- **Порт:** 9001 (health check)
- **Процессы:** 
  - Telegram bot polling (команды пользователей)
  - APScheduler (уведомления 10:00/15:00/21:00)
  - Health check HTTP сервер

### 🌐 Webhook Server (порт 9000)
- **Функции:** Прием и обработка webhooks от KeyCRM
- **Запуск:** `uvicorn src.webhook.app:app --host 0.0.0.0 --port 9000`
- **Порт:** 9000 (KeyCRM webhooks)
- **Процессы:**
  - FastAPI webhook endpoint `/webhook/keycrm`
  - Обработка заказов KeyCRM → расход заготовок
  - Обновление Google Sheets

---

## 🔧 Подготовка к деплою

### 1. Настройка переменных окружения

```bash
# Скопируйте шаблон конфигурации
cp .env.template .env

# Отредактируйте .env с вашими данными
nano .env
```

**Обязательные параметры:**
```bash
# KeyCRM
KEYCRM_API_TOKEN=your_token_here
KEYCRM_WEBHOOK_SECRET=your_secret_here

# Google Sheets
GSHEETS_ID=your_sheets_id_here  
GOOGLE_CREDENTIALS_JSON={"type":"service_account",...}

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
TELEGRAM_ALLOWED_USERS=[123456789]
TELEGRAM_ADMIN_USERS=[123456789]

# Webhook endpoint (замените на ваш домен)
WEBHOOK_ENDPOINT=https://yourdomain.com/webhook/keycrm
```

### 2. Подготовка сервера

```bash
# Создание директории проекта
sudo mkdir -p /opt/docker-projects/warehouse-automation
cd /opt/docker-projects/warehouse-automation

# Клонирование репозитория
git clone https://github.com/your-username/warehouse-automation .

# Создание директорий для логов
sudo mkdir -p logs/telegram logs/webhook
sudo chown -R $(whoami):$(whoami) logs/
```

---

## 🚀 Деплой с Docker Compose

### Вариант A: Полный деплой (рекомендуется)

```bash
# 1. Сборка и запуск обоих сервисов
docker-compose up -d --build

# 2. Проверка статуса
docker-compose ps

# 3. Просмотр логов
docker-compose logs -f telegram-bot
docker-compose logs -f webhook-server

# 4. Проверка health checks
curl http://localhost:9001/health  # Telegram bot
curl http://localhost:9000/health  # Webhook server
```

### Вариант B: Раздельный запуск

```bash
# Только Telegram bot
docker-compose up -d telegram-bot

# Только Webhook server  
docker-compose up -d webhook-server

# Остановка конкретного сервиса
docker-compose stop telegram-bot
```

---

## 🔍 Проверка работы системы

### Health Check Endpoints

```bash
# Telegram bot health check
curl http://localhost:9001/health
# Ответ: {"status": "healthy", "uptime_seconds": 123, ...}

# Webhook server health check  
curl http://localhost:9000/health
# Ответ: {"status": "healthy", "services": {"keycrm": "connected"}}

# Готовность webhook сервера
curl http://localhost:9000/ready
```

### Проверка логов

```bash
# Реальное время
docker-compose logs -f telegram-bot
docker-compose logs -f webhook-server

# Последние 100 строк
docker-compose logs --tail=100 telegram-bot

# Поиск ошибок
docker-compose logs telegram-bot | grep ERROR
```

### Тест функций

```bash
# 1. Проверьте Telegram бот
# Отправьте /start в Telegram

# 2. Проверьте webhook (если есть тестовые данные)
curl -X POST http://localhost:9000/webhook/keycrm \
  -H "Content-Type: application/json" \
  -d '{"test": "data"}'
```

---

## 📊 Мониторинг системы

### Docker статистика

```bash
# Использование ресурсов
docker stats warehouse-telegram-bot warehouse-webhook-server

# Статус контейнеров
docker-compose ps

# Перезапуск при необходимости
docker-compose restart telegram-bot
docker-compose restart webhook-server
```

### Системные логи

```bash
# Логи из файлов (если настроены)
tail -f logs/telegram/app.log
tail -f logs/webhook/app.log

# Ротация логов Docker (уже настроена)
# max-size: 10m, max-file: 3
```

---

## 🔧 Управление системой

### Обновление кода

```bash
# 1. Получение обновлений
git pull origin master

# 2. Пересборка и перезапуск  
docker-compose down
docker-compose up -d --build

# 3. Проверка
docker-compose logs -f
```

### Бэкап данных

```bash
# Экспорт переменных окружения
cp .env .env.backup.$(date +%Y%m%d)

# Остановка для консистентного бэкапа
docker-compose stop

# Архивация важных данных
tar -czf backup.$(date +%Y%m%d).tar.gz logs/ data/ .env

# Запуск после бэкапа
docker-compose up -d
```

### Откат к предыдущей версии

```bash
# 1. Остановка текущей версии
docker-compose down

# 2. Откат кода
git checkout <previous-commit-hash>

# 3. Пересборка и запуск
docker-compose up -d --build
```

---

## ⚠️ Устранение неполадок

### Проблемы с портами

```bash
# Проверка занятости портов
netstat -tlnp | grep :9000
netstat -tlnp | grep :9001

# Если порты заняты, измените в docker-compose.yml:
# ports: ["9002:9000", "9003:9001"]
```

### Проблемы с доступами

```bash
# Права на директории
sudo chown -R $(whoami):$(whoami) logs/ data/

# Права на .env
chmod 600 .env

# Проверка Docker permissions
sudo usermod -aG docker $USER
# Перелогинтесь после этой команды
```

### Проблемы с зависимостями

```bash
# Принудительная пересборка без кэша
docker-compose build --no-cache

# Очистка Docker кэша
docker system prune -f

# Проверка образа
docker-compose exec telegram-bot pip list
docker-compose exec webhook-server pip list
```

### KeyCRM Webhook настройка

1. **В KeyCRM панели:**
   - Настройки → Интеграции → Webhooks
   - URL: `https://yourdomain.com/webhook/keycrm`
   - События: `order.created`, `order.updated`
   - Метод: POST

2. **Проверка получения webhooks:**
   ```bash
   docker-compose logs webhook-server | grep "webhook"
   ```

---

## 📋 Чеклист успешного деплоя

- [ ] **.env файл настроен** с реальными токенами
- [ ] **Порты 9000/9001 свободны** на сервере  
- [ ] **Docker и docker-compose установлены**
- [ ] **Директории logs/ созданы** с правильными правами
- [ ] **Git репозиторий обновлен** до последней версии
- [ ] **Health checks отвечают** 200 OK
- [ ] **Telegram бот отвечает** на /start
- [ ] **KeyCRM webhook настроен** (если используется)
- [ ] **Google Sheets доступны** через API
- [ ] **Логи пишутся** без ошибок
- [ ] **APScheduler работает** (проверить в 10:00/15:00/21:00)

---

## 🌐 Настройка поддомена для Webhook

### Вариант A: Nginx Reverse Proxy

1. **Создайте конфигурацию Nginx:**

```nginx
# /etc/nginx/sites-available/warehouse-webhook
server {
    listen 80;
    server_name warehouse.yourdomain.com;

    # Перенаправление на HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name warehouse.yourdomain.com;

    # SSL сертификаты (Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/warehouse.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/warehouse.yourdomain.com/privkey.pem;

    # Безопасность SSL
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers on;

    # Webhook endpoint (KeyCRM)
    location /webhook/keycrm {
        proxy_pass http://localhost:9000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Webhook специфичные настройки
        proxy_read_timeout 30s;
        proxy_connect_timeout 10s;
        client_max_body_size 1M;
        
        # Логирование webhook запросов
        access_log /var/log/nginx/warehouse-webhook.access.log;
        error_log /var/log/nginx/warehouse-webhook.error.log;
    }

    # Health check endpoint (опционально для мониторинга)
    location /health {
        proxy_pass http://localhost:9000;
        access_log off;
    }

    # Блокируем все остальные запросы
    location / {
        return 404;
    }
}
```

2. **Активируйте конфигурацию:**

```bash
# Создание символической ссылки
sudo ln -s /etc/nginx/sites-available/warehouse-webhook /etc/nginx/sites-enabled/

# Проверка конфигурации
sudo nginx -t

# Перезагрузка Nginx
sudo systemctl reload nginx
```

3. **Получите SSL сертификат (Let's Encrypt):**

```bash
# Установка Certbot
sudo apt install certbot python3-certbot-nginx

# Получение сертификата
sudo certbot --nginx -d warehouse.yourdomain.com

# Автообновление сертификата (добавится автоматически в cron)
sudo certbot renew --dry-run
```

### Вариант B: Cloudflare Tunnel (рекомендуется)

1. **Установите cloudflared:**

```bash
# Ubuntu/Debian
wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared-linux-amd64.deb
```

2. **Авторизация и создание туннеля:**

```bash
# Логин в Cloudflare
cloudflared tunnel login

# Создание туннеля
cloudflared tunnel create warehouse-automation

# Настройка DNS записи
cloudflared tunnel route dns warehouse-automation warehouse.yourdomain.com
```

3. **Конфигурация туннеля:**

```yaml
# ~/.cloudflared/config.yml
tunnel: warehouse-automation
credentials-file: /home/user/.cloudflared/YOUR_TUNNEL_ID.json

ingress:
  - hostname: warehouse.yourdomain.com
    service: http://localhost:9000
    path: /webhook/keycrm
  - hostname: warehouse.yourdomain.com  
    service: http://localhost:9000
    path: /health
  - service: http_status:404
```

4. **Запуск туннеля как сервиса:**

```bash
# Установка как системный сервис
sudo cloudflared service install

# Запуск
sudo systemctl start cloudflared
sudo systemctl enable cloudflared

# Проверка статуса
sudo systemctl status cloudflared
```

### Настройка KeyCRM Webhook

1. **В панели KeyCRM:**
   - Перейдите в **Настройки → Интеграции → Webhooks**
   - **URL:** `https://warehouse.yourdomain.com/webhook/keycrm`
   - **События:** `order.created`, `order.updated`, `order.status_changed`
   - **Метод:** POST
   - **Формат:** JSON

2. **Тестирование webhook:**

```bash
# Проверка доступности извне
curl -X POST https://warehouse.yourdomain.com/webhook/keycrm \
  -H "Content-Type: application/json" \
  -d '{"event": "test", "context": {}}'

# Мониторинг в реальном времени
docker-compose logs -f webhook-server | grep webhook
```

### Безопасность Webhook

1. **Firewall настройки:**

```bash
# Разрешаем только необходимые порты
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80
sudo ufw allow 443

# НЕ открываем порты 9000/9001 наружу
# Они доступны только через reverse proxy
sudo ufw enable
```

2. **Проверка безопасности:**

```bash
# Проверяем что порты 9000/9001 НЕ доступны извне
nmap -p 9000,9001 your-server-ip

# Должны быть filtered или closed
```

3. **Monitoring и алерты:**

```bash
# Мониторинг webhook запросов в Nginx
tail -f /var/log/nginx/warehouse-webhook.access.log

# Алерты при ошибках (настроить через logwatch или аналог)
grep "ERROR" /var/log/nginx/warehouse-webhook.error.log
```

### Обновление .env файла

После настройки поддомена обновите `.env`:

```bash
# В файле .env
WEBHOOK_ENDPOINT=https://warehouse.yourdomain.com/webhook/keycrm

# Перезапуск сервисов после изменения
docker-compose down
docker-compose up -d
```

---

## 📞 Поддержка

При проблемах с деплоем:

1. **Проверьте логи:** `docker-compose logs -f`
2. **Проверьте health checks:** `curl localhost:9001/health`  
3. **Проверьте переменные окружения:** `.env` файл
4. **Проверьте сетевое соединение:** доступ к KeyCRM/Telegram API
5. **Проверьте права доступа:** `ls -la logs/ data/`

**Полезные команды для отладки:**

```bash
# Вход в контейнер для отладки
docker-compose exec telegram-bot bash
docker-compose exec webhook-server bash

# Проверка переменных окружения в контейнере  
docker-compose exec telegram-bot env | grep TELEGRAM

# Ручной тест планировщика
docker-compose exec telegram-bot python -c "from src.scheduler.runner import get_scheduler_runner; print('OK')"
```