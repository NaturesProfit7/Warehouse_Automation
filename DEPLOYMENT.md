# 🚀 Деплой Warehouse Automation System

## 📋 Быстрый старт

### 1. DNS настройка (ПЕРВЫМ ДЕЛОМ!)

В панели управления доменом `timosh-design.com`:
```
Тип: A
Имя: warehouse  
Значение: 146.103.108.73
TTL: 300
```

### 2. Подготовка сервера

```bash
# SSH подключение
ssh root@146.103.108.73

# Удаляем старую директорию (если есть)
rm -rf /opt/docker-projects/warehouse-automation

# Создаем правильную структуру
mkdir -p /opt/docker-projects/warehouse-automation
cd /opt/docker-projects/warehouse-automation

# Клонируем репозиторий (ВАЖНО: точка в конце!)
git clone https://github.com/NaturesProfit7/Warehouse_Automation .

# Проверяем что файлы на месте
ls -la docker-compose.yml

# Создаем директории для логов
mkdir -p logs/telegram logs/webhook
```

### 3. Настройка переменных окружения

```bash
# Копируем шаблон
cp .env.template .env

# Редактируем (заполняем реальными данными)
nano .env
```

**Обязательные переменные:**
```bash
KEYCRM_API_TOKEN=ваш_токен_keycrm
KEYCRM_WEBHOOK_SECRET=ваш_секретный_ключ
GSHEETS_ID=ваш_id_google_sheets
GOOGLE_CREDENTIALS_JSON={"type":"service_account",...}
TELEGRAM_BOT_TOKEN=ваш_токен_бота
TELEGRAM_CHAT_ID=ваш_chat_id
TELEGRAM_ALLOWED_USERS=[ваш_user_id]
TELEGRAM_ADMIN_USERS=[ваш_user_id]
WEBHOOK_ENDPOINT=https://warehouse.timosh-design.com/webhook/keycrm
```

### 4. Установка Docker (если нужно)

```bash
# Проверка Docker
docker --version

# Если Docker нет:
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
```

### 5. Настройка Nginx + SSL

```bash
# Установка
apt update && apt install nginx certbot python3-certbot-nginx -y

# Создание конфигурации
nano /etc/nginx/sites-available/warehouse
```

**Содержимое конфигурации (ВРЕМЕННО, только HTTP):**
```nginx
server {
    listen 80;
    server_name warehouse.timosh-design.com;

    location /webhook/keycrm {
        proxy_pass http://localhost:9000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /health {
        proxy_pass http://localhost:9000;
        access_log off;
    }

    location / {
        return 404;
    }
}
```

**Активация и получение SSL:**
```bash
# Активируем конфигурацию
ln -s /etc/nginx/sites-available/warehouse /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx

# Получаем SSL сертификат (Certbot автоматически обновит конфигурацию)
certbot --nginx -d warehouse.timosh-design.com

# Проверяем
nginx -t
systemctl reload nginx
```

### 6. Настройка Firewall

```bash
ufw allow ssh && ufw allow 80 && ufw allow 443
ufw --force enable
```

### 7. Запуск системы

```bash
cd /opt/docker-projects/warehouse-automation

# ⚠️ ВАЖНО: Останавливаем старые контейнеры для избежания конфликтов
docker compose down

# Запуск с исправлениями стабильности
docker compose up -d --build

# Проверка статуса
docker compose ps

# ✅ Ждем запуска (~60 секунд для полной инициализации)
sleep 60
```

### 8. Проверка работы

```bash
# Локальные health checks
curl http://localhost:9001/health  # Telegram bot
curl http://localhost:9000/health  # Webhook server

# Внешний доступ  
curl https://warehouse.timosh-design.com/health

# Мониторинг логов
docker compose logs -f telegram-bot    # Telegram bot + планировщик
docker compose logs -f webhook-server  # KeyCRM webhooks

# Проверка на ошибки
docker compose logs telegram-bot | grep ERROR
docker compose logs webhook-server | grep ERROR
```

### 9. Настройка KeyCRM webhook

В панели KeyCRM → Интеграции → Webhooks:
- **URL:** `https://warehouse.timosh-design.com/webhook/keycrm`
- **События:** order.created, order.updated
- **Метод:** POST

## 🔧 Управление системой

```bash
# Полная остановка
docker compose down

# Мягкий перезапуск (без пересборки)
docker compose restart

# Перезапуск конкретного сервиса
docker compose restart telegram-bot
docker compose restart webhook-server

# Обновление кода из GitHub
git pull && docker compose down && docker compose up -d --build

# Просмотр логов в реальном времени
docker compose logs -f telegram-bot webhook-server

# Проверка статуса сервисов
docker compose ps
docker compose top

# Очистка системы (при необходимости)
docker system prune -f
```

## 📊 Мониторинг

```bash
# Health checks
watch -n 5 'curl -s http://localhost:9001/health | jq'
watch -n 5 'curl -s http://localhost:9000/health | jq'

# Статистика ресурсов
docker stats --no-stream

# Последние ошибки
docker compose logs --tail=50 telegram-bot | grep ERROR
docker compose logs --tail=50 webhook-server | grep ERROR
```

## 🚨 Решение проблем

```bash
# Если видишь "Conflict: terminated by other getUpdates request":
docker compose restart telegram-bot

# Если контейнеры не стартуют:
docker compose down && docker compose up -d --build

# Проверка ресурсов системы:
docker system df
free -h

# Просмотр детальных логов:
docker compose logs --tail=100 telegram-bot
docker compose logs --tail=100 webhook-server
```

## ✅ Важные исправления в системе

- **Устранен конфликт Telegram bot instances** с проверкой единственности
- **Оптимизированы health checks** с увеличенными интервалами
- **Улучшена последовательность запуска** сервисов
- **Разделены сервисы** на отдельные порты (9000/9001)

**🎉 Готово! Система работает на https://warehouse.timosh-design.com/**