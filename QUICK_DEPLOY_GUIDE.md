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
mkdir -p /opt/docker-projects/warehouse-automation
cd /opt/docker-projects/warehouse-automation
git clone https://github.com/your-username/warehouse-automation .
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

### Конфигурация Nginx:
```bash
nano /etc/nginx/sites-available/warehouse
```

**Содержимое файла:**
```nginx
server {
    listen 80;
    server_name warehouse.timosh-design.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name warehouse.timosh-design.com;

    ssl_certificate /etc/letsencrypt/live/warehouse.timosh-design.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/warehouse.timosh-design.com/privkey.pem;

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

### Активация:
```bash
ln -s /etc/nginx/sites-available/warehouse /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
certbot --nginx -d warehouse.timosh-design.com
```

## 🔥 **4. Firewall**
```bash
ufw allow ssh && ufw allow 80 && ufw allow 443
ufw --force enable
```

## 🚀 **5. Запуск системы**
```bash
cd /opt/docker-projects/warehouse-automation
docker-compose up -d --build
docker-compose ps
```

## ✅ **6. Проверка**
```bash
# Локально
curl http://localhost:9001/health
curl http://localhost:9000/health

# Внешний доступ  
curl https://warehouse.timosh-design.com/health

# Логи
docker-compose logs -f telegram-bot
docker-compose logs -f webhook-server
```

## 🎯 **7. KeyCRM настройка**

В панели KeyCRM → Интеграции → Webhooks:
- **URL:** `https://warehouse.timosh-design.com/webhook/keycrm`
- **События:** order.created, order.updated
- **Метод:** POST

## 🔧 **Управление**

```bash
# Остановка
docker-compose down

# Перезапуск  
docker-compose restart

# Обновление кода
git pull && docker-compose up -d --build

# Логи ошибок
docker-compose logs telegram-bot | grep ERROR
```

**🎉 Готово! Система работает на https://warehouse.timosh-design.com/**