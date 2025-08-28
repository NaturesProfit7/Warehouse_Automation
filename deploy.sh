#!/bin/bash

# Скрипт автоматического деплоя Warehouse Automation System
# Использование: ./deploy.sh [command]

set -e

PROJECT_NAME="warehouse-automation"
COMPOSE_FILE="docker-compose.yml"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Проверка зависимостей
check_dependencies() {
    log_info "Проверка зависимостей..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker не установлен!"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose не установлен!"
        exit 1
    fi
    
    if ! command -v git &> /dev/null; then
        log_error "Git не установлен!"
        exit 1
    fi
    
    log_success "Все зависимости установлены"
}

# Остановка приложения
stop() {
    log_info "Остановка $PROJECT_NAME..."
    docker-compose -f $COMPOSE_FILE down
    log_success "Приложение остановлено"
}

# Обновление кода
update_code() {
    log_info "Обновление кода из Git..."
    git fetch origin
    git reset --hard origin/main
    log_success "Код обновлен"
}

# Сборка образов
build() {
    log_info "Сборка Docker образов..."
    docker-compose -f $COMPOSE_FILE build --no-cache
    log_success "Образы собраны"
}

# Запуск приложения
start() {
    log_info "Запуск $PROJECT_NAME..."
    docker-compose -f $COMPOSE_FILE up -d
    log_success "Приложение запущено"
}

# Проверка статуса
status() {
    log_info "Проверка статуса..."
    docker-compose -f $COMPOSE_FILE ps
    echo
    log_info "Логи последние 20 строк:"
    docker-compose -f $COMPOSE_FILE logs --tail=20 warehouse-bot
}

# Полный деплой
deploy() {
    log_info "Начинаем полный деплой $PROJECT_NAME..."
    
    check_dependencies
    stop
    update_code
    build
    start
    
    log_info "Ожидание запуска сервисов..."
    sleep 15
    
    status
    
    # Проверка здоровья
    if docker-compose ps | grep -q "Up"; then
        log_success "✅ Деплой успешно завершен!"
    else
        log_error "❌ Деплой завершен с ошибками"
        exit 1
    fi
}

# Просмотр логов
logs() {
    log_info "Просмотр логов $PROJECT_NAME..."
    docker-compose -f $COMPOSE_FILE logs -f warehouse-bot
}

# Перезапуск
restart() {
    log_info "Перезапуск $PROJECT_NAME..."
    stop
    start
    sleep 10
    status
    log_success "Перезапуск завершен"
}

# Очистка
cleanup() {
    log_info "Очистка неиспользуемых образов и контейнеров..."
    docker system prune -f
    docker image prune -a -f
    log_success "Очистка завершена"
}

# Резервное копирование
backup() {
    log_info "Создание резервной копии..."
    BACKUP_DIR="./backups"
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_FILE="$BACKUP_DIR/warehouse_backup_$TIMESTAMP.tar.gz"
    
    mkdir -p $BACKUP_DIR
    
    tar -czf $BACKUP_FILE \
        --exclude='.git' \
        --exclude='venv*' \
        --exclude='__pycache__' \
        --exclude='*.pyc' \
        ./
    
    log_success "Резервная копия создана: $BACKUP_FILE"
}

# Показать помощь
show_help() {
    echo "Warehouse Automation Deployment Script"
    echo ""
    echo "Использование: $0 [command]"
    echo ""
    echo "Команды:"
    echo "  deploy      - Полный деплой (остановка, обновление, сборка, запуск)"
    echo "  start       - Запуск приложения"
    echo "  stop        - Остановка приложения"
    echo "  restart     - Перезапуск приложения"
    echo "  status      - Проверка статуса и логов"
    echo "  logs        - Просмотр логов в реальном времени"
    echo "  build       - Сборка Docker образов"
    echo "  update      - Обновление кода из Git"
    echo "  cleanup     - Очистка неиспользуемых Docker объектов"
    echo "  backup      - Создание резервной копии"
    echo "  help        - Показать эту справку"
    echo ""
}

# Основная логика
case "${1:-}" in
    "deploy")
        deploy
        ;;
    "start")
        start
        ;;
    "stop")
        stop
        ;;
    "restart")
        restart
        ;;
    "status")
        status
        ;;
    "logs")
        logs
        ;;
    "build")
        build
        ;;
    "update")
        update_code
        ;;
    "cleanup")
        cleanup
        ;;
    "backup")
        backup
        ;;
    "help"|"--help"|"-h")
        show_help
        ;;
    "")
        log_warning "Команда не указана"
        show_help
        exit 1
        ;;
    *)
        log_error "Неизвестная команда: $1"
        show_help
        exit 1
        ;;
esac