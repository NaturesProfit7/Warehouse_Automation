# 🚀 Полное руководство по деплою Warehouse Automation System

## 📋 Содержание
1. [Подготовка VPS Ubuntu](#1-подготовка-vps-ubuntu)
2. [Настройка поддомена и SSL](#2-настройка-поддомена-и-ssl)
3. [Установка Docker и зависимостей](#3-установка-docker-и-зависимостей)
4. [Настройка GitHub Actions (CI/CD)](#4-настройка-github-actions-cicd)
5. [Конфигурация переменных окружения](#5-конфигурация-переменных-окружения)
6. [Первоначальный деплой](#6-первоначальный-деплой)
7. [Мониторинг и управление](#7-мониторинг-и-управление)

---

## 1. Подготовка VPS Ubuntu

### 1.1. Минимальные требования
- **ОС**: Ubuntu 20.04 LTS или новее
- **RAM**: 1GB (рекомендуется 2GB)
- **Диск**: 10GB свободного места
- **CPU**: 1 core (рекомендуется 2 cores)

### 1.2. Подключение к серверу
```bash
# Подключение по SSH (замените на ваши данные)
ssh root@YOUR_SERVER_IP
```

### 1.3. Обновление системы
```bash
# Обновление пакетов
sudo apt update && sudo apt upgrade -y

# Установка базовых утилит
sudo apt install -y curl wget git unzip software-properties-common
```

---

## 2. Настройка поддомена и SSL

### 2.1. Настройка DNS записи
**У вашего DNS провайдера:**
1. Добавьте A-запись:
   ```
   Тип: A
   Имя: blanks (или warehouse)
   Значение: YOUR_SERVER_IP
   TTL: Auto
   ```

### 2.2. Установка Nginx
```bash
# Установка Nginx
sudo apt install -y nginx

# Создание конфигурации
sudo nano /etc/nginx/sites-available/warehouse
```

**Содержимое файла:**
```nginx
server {
    listen 80;
    server_name blanks.yourdomain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /webhook/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 2.3. Активация конфигурации
```bash
# Активация сайта
sudo ln -s /etc/nginx/sites-available/warehouse /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl enable nginx
```

### 2.4. SSL сертификат (Let's Encrypt)
```bash
# Установка Certbot
sudo apt install -y certbot python3-certbot-nginx

# Получение SSL сертификата
sudo certbot --nginx -d blanks.yourdomain.com

# Автообновление сертификатов
sudo crontab -e
# Добавьте: 0 12 * * * /usr/bin/certbot renew --quiet
```

---

## 3. Установка Docker и зависимостей

### 3.1. Установка Docker
```bash
# Удаление старых версий
sudo apt remove docker docker-engine docker.io containerd runc

# Добавление репозитория Docker
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Установка Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io

# Добавление пользователя в группу docker
sudo usermod -aG docker $USER
newgrp docker

# Проверка установки
docker --version
```

### 3.2. Установка Docker Compose
```bash
# Скачивание Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.21.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose

# Права на выполнение
sudo chmod +x /usr/local/bin/docker-compose

# Проверка
docker-compose --version
```

### 3.3. Автозапуск Docker
```bash
sudo systemctl enable docker
sudo systemctl start docker
```

---

## 4. Настройка GitHub Actions (CI/CD)

### 4.1. Создание SSH ключей

**На сервере:**
```bash
# Генерация SSH ключа
ssh-keygen -t rsa -b 4096 -C "deploy@warehouse" -f ~/.ssh/warehouse_deploy

# Добавление в authorized_keys
cat ~/.ssh/warehouse_deploy.pub >> ~/.ssh/authorized_keys

# Показать приватный ключ (скопируйте)
cat ~/.ssh/warehouse_deploy
```

### 4.2. GitHub Secrets

**В GitHub репозитории → Settings → Secrets:**
```
VPS_HOST = YOUR_SERVER_IP
VPS_USER = ubuntu (или ваш пользователь)
VPS_PRIVATE_KEY = (содержимое ~/.ssh/warehouse_deploy)
PROJECT_PATH = /home/ubuntu/Warehouse_Automation
```

### 4.3. Клонирование репозитория
```bash
# Клонирование
cd ~
git clone https://github.com/YOUR_USERNAME/Warehouse_Automation.git
cd Warehouse_Automation

# Создание папок
mkdir -p logs data backups
```

---

## 5. Конфигурация переменных окружения

### 5.1. Создание .env
```bash
nano .env
```

**Содержимое .env:**
```env
# KeyCRM интеграция
KEYCRM_API_TOKEN=your_token
KEYCRM_WEBHOOK_SECRET=your_secret

# Google Sheets
GSHEETS_ID=your_sheets_id
GOOGLE_CREDENTIALS_JSON={"type":"service_account",...}

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
TELEGRAM_ALLOWED_USERS=[7373293370]
TELEGRAM_ADMIN_USERS=[7373293370]

# Webhook endpoint
WEBHOOK_ENDPOINT=https://blanks.yourdomain.com/webhook/keycrm

# Параметры
TIMEZONE=Europe/Kyiv
LOG_LEVEL=INFO
DEBUG=false
```

### 5.2. Права доступа
```bash
chmod 600 .env
```

---

## 6. Первоначальный деплой

### 6.1. Ручной деплой
```bash
cd ~/Warehouse_Automation

# Деплой одной командой
./deploy.sh deploy

# Или пошагово:
docker-compose build
docker-compose up -d
```

### 6.2. Проверка
```bash
# Статус контейнеров
docker-compose ps

# Логи
docker-compose logs warehouse-bot

# Управление
./deploy.sh status
./deploy.sh logs
```

---

## 7. Мониторинг и управление

### 7.1. Команды управления
```bash
./deploy.sh deploy    # Полный деплой
./deploy.sh start     # Запуск
./deploy.sh stop      # Остановка
./deploy.sh restart   # Перезапуск
./deploy.sh status    # Статус
./deploy.sh logs      # Логи
./deploy.sh backup    # Бэкап
./deploy.sh cleanup   # Очистка
```

### 7.2. Автоматическое резервное копирование
```bash
crontab -e
# Добавить: 0 3 * * * cd /home/ubuntu/Warehouse_Automation && ./deploy.sh backup
```

---

## 🎉 Готово!

После выполнения всех шагов:

✅ Полностью контейнеризованная система  
✅ Автодеплой при push в GitHub  
✅ SSL сертификат и поддомен  
✅ Мониторинг и логирование  
✅ Резервное копирование  

**Telegram бот будет доступен сразу после деплоя!** 🤖

### Быстрые команды:
```bash
# Проверка системы
./deploy.sh status

# Обновление
git pull && ./deploy.sh deploy

# Логи в реальном времени  
./deploy.sh logs
```