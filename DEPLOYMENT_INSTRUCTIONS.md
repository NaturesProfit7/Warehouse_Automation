# 🚀 Деплой Warehouse Automation - VPS Ubuntu

## 📋 Пошаговая инструкция

### **Шаг 1: DNS настройка**

В панели управления доменом `timosh-design.com` создай **A-запись**:
```
warehouse.timosh-design.com → 146.103.108.73
```

### **Шаг 2: Подготовка сервера**

```bash
# SSH на сервер
ssh root@146.103.108.73

# Создание директории проекта
mkdir -p /opt/docker-projects/warehouse-automation
cd /opt/docker-projects/warehouse-automation

# Клонирование репозитория
git clone https://github.com/your-username/warehouse-automation .

# Создание директорий
mkdir -p logs/telegram logs/webhook
```

### **Шаг 3: Настройка .env файла**

```bash
# Копирование шаблона
cp .env.template .env

# Редактирование (вставь свои токены)
nano .env
```

**Обязательные параметры в .env:**
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

# Webhook endpoint
WEBHOOK_ENDPOINT=https://warehouse.timosh-design.com/webhook/keycrm
```

### **Шаг 4: Настройка Nginx**

```bash
# Установка Nginx
apt update && apt install nginx -y

# Создание конфигурации
nano /etc/nginx/sites-available/warehouse
```

**Вставь конфигурацию:**
```nginx
server {
    listen 80;
    server_name warehouse.timosh-design.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name warehouse.timosh-design.com;

    # SSL сертификаты (Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/warehouse.timosh-design.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/warehouse.timosh-design.com/privkey.pem;

    # Webhook endpoint
    location /webhook/keycrm {
        proxy_pass http://localhost:9000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Health check
    location /health {
        proxy_pass http://localhost:9000;
        access_log off;
    }

    location / {
        return 404;
    }
}
```

**Активация сайта:**
```bash
# Включение сайта
ln -s /etc/nginx/sites-available/warehouse /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
```

### **Шаг 5: SSL сертификат**

```bash
# Установка Certbot
apt install certbot python3-certbot-nginx -y

# Получение сертификата
certbot --nginx -d warehouse.timosh-design.com
```

### **Шаг 6: Firewall**

```bash
# Настройка UFW
ufw allow ssh
ufw allow 80
ufw allow 443
ufw --force enable

# Порты 9000/9001 НЕ открываем - только через Nginx
```

### **Шаг 7: Запуск системы**

```bash
# Возвращаемся в директорию проекта
cd /opt/docker-projects/warehouse-automation

# Запуск обоих сервисов
docker-compose up -d --build

# Проверка
docker-compose ps
```

### **Шаг 8: Проверка работы**

```bash
# Локальные health checks
curl http://localhost:9001/health  # Telegram bot
curl http://localhost:9000/health  # Webhook server

# Внешний доступ
curl https://warehouse.timosh-design.com/health

# Логи
docker-compose logs -f
```

### **Шаг 9: KeyCRM настройка**

В панели KeyCRM:
- **URL:** `https://warehouse.timosh-design.com/webhook/keycrm`
- **События:** `order.created`, `order.updated`
- **Метод:** POST

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