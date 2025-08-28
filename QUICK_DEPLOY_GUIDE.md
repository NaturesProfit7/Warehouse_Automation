# ⚡ Быстрый деплой - warehouse.timosh-design.com

## 🎯 **1. DNS запись (ПЕРВЫМ ДЕЛОМ!)**

В панели управления доменом `timosh-design.com`:
```
Тип: A
Имя: warehouse  
Значение: 146.103.108.73
TTL: 300
```

## 🖥️ **2. На сервере (SSH: root@146.103.108.73)**

### Подготовка:
```bash
# Удаляем старую директорию (если есть)
rm -rf /opt/docker-projects/warehouse-automation

# Создаем правильную структуру
mkdir -p /opt/docker-projects/warehouse-automation
cd /opt/docker-projects/warehouse-automation

# Клонируем в текущую директорию (ВАЖНО: точка в конце!)
git clone https://github.com/NaturesProfit7/Warehouse_Automation .

# Проверяем что файлы на месте
ls -la docker-compose.yml

# Создаем директории для логов
mkdir -p logs/telegram logs/webhook
```

### Настройка .env:
```bash
cp .env.template .env
nano .env
```

**Замени в .env файле:**
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

## 🌐 **3. Nginx + SSL**

### Установка и настройка:
```bash
apt update && apt install nginx certbot python3-certbot-nginx -y
```

### ВРЕМЕННАЯ конфигурация Nginx (без SSL):
```bash
nano /etc/nginx/sites-available/warehouse
```

**Содержимое файла (ВРЕМЕННО, только HTTP):**
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

### Активация и получение SSL:
```bash
# Активируем временную конфигурацию
ln -s /etc/nginx/sites-available/warehouse /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx

# СНАЧАЛА получаем SSL сертификат
certbot --nginx -d warehouse.timosh-design.com

# Certbot АВТОМАТИЧЕСКИ обновит конфигурацию с HTTPS
# Проверяем что все ОК
nginx -t
systemctl reload nginx
```

## 🔥 **4. Firewall**
```bash
ufw allow ssh && ufw allow 80 && ufw allow 443
ufw --force enable
```

## 🚀 **5. Установка Docker (если нужно)**
```bash
# Проверка Docker
docker --version

# Если Docker нет, быстрая установка:
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
```

## 🚀 **6. Запуск системы**
```bash
cd /opt/docker-projects/warehouse-automation

# Проверяем что docker-compose.yml на месте
ls -la docker-compose.yml

# ⚠️ ВАЖНО: Останавливаем старые контейнеры для избежания конфликтов
docker compose down

# Запуск с новыми исправлениями (используем новый синтаксис)
docker compose up -d --build

# Проверка статуса
docker compose ps

# ✅ Ждем запуска (~ 60 секунд для полной инициализации)
echo "Ожидание запуска сервисов..."
sleep 60
```

## ✅ **7. Проверка**
```bash
# Локально (health checks)
curl http://localhost:9001/health  # Telegram bot
curl http://localhost:9000/health  # Webhook server

# Внешний доступ  
curl https://warehouse.timosh-design.com/health

# 📋 Логи (мониторинг запуска)
docker compose logs -f telegram-bot    # Telegram bot + планировщик
docker compose logs -f webhook-server  # KeyCRM webhooks

# 🔍 Проверка на ошибки
docker compose logs telegram-bot | grep ERROR
docker compose logs webhook-server | grep ERROR
```

### 🚨 **Решение проблем:**
```bash
# Если видишь "Conflict: terminated by other getUpdates request":
docker compose restart telegram-bot

# Если контейнеры не стартуют:
docker compose down && docker compose up -d --build

# Проверка ресурсов системы:
docker system df
free -h
```

## 🎯 **8. KeyCRM настройка**

В панели KeyCRM → Интеграции → Webhooks:
- **URL:** `https://warehouse.timosh-design.com/webhook/keycrm`
- **События:** order.created, order.updated
- **Метод:** POST

## 🔧 **Управление**

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

## 📊 **Мониторинг**

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

**🎉 Готово! Система работает на https://warehouse.timosh-design.com/**

## ⚠️ **Важные исправления в этой версии:**
- Устранен конфликт Telegram bot instances
- Оптимизированы health checks для стабильности
- Добавлена проверка единственности экземпляра бота
- Улучшена последовательность запуска сервисов