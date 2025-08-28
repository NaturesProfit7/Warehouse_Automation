# 🔄 GitHub Actions CI/CD Setup

## Проблема
GitHub блокирует создание workflow файлов через OAuth App без специального scope `workflow`. Поэтому нужно добавить файл вручную.

## 🛠️ Решение: Добавление GitHub Actions вручную

### 1. Создание workflow файла

В GitHub репозитории создайте файл `.github/workflows/deploy.yml` со следующим содержимым:

```yaml
name: Deploy Warehouse Automation

on:
  push:
    branches: [ main, master ]
  pull_request:
    branches: [ main, master ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python 3.12
      uses: actions/setup-python@v4
      with:
        python-version: '3.12'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest pytest-asyncio pytest-cov
    
    - name: Run tests
      run: |
        pytest tests/ -v --cov=src --cov-report=xml
    
    - name: Code quality checks
      run: |
        pip install ruff mypy
        ruff check src/
        mypy src/ --ignore-missing-imports

  deploy:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main' || github.ref == 'refs/heads/master'
    
    steps:
    - name: Deploy to VPS
      uses: appleboy/ssh-action@v1.0.0
      with:
        host: ${{ secrets.VPS_HOST }}
        username: ${{ secrets.VPS_USER }}
        key: ${{ secrets.VPS_PRIVATE_KEY }}
        script: |
          cd ${{ secrets.PROJECT_PATH || '/home/ubuntu/Warehouse_Automation' }}
          git pull origin main
          ./deploy.sh deploy
          
          # Проверка успешности деплоя
          sleep 30
          if ! docker-compose ps | grep -q "Up"; then
            echo "❌ Деплой неуспешен - контейнер не запущен"
            exit 1
          fi
          
          echo "✅ Деплой успешно завершен"
```

### 2. Настройка GitHub Secrets

В вашем GitHub репозитории перейдите в **Settings → Secrets and variables → Actions** и добавьте:

| Secret Name | Description | Example Value |
|-------------|-------------|---------------|
| `VPS_HOST` | IP адрес вашего VPS сервера | `123.456.789.10` |
| `VPS_USER` | Пользователь для SSH подключения | `ubuntu` |
| `VPS_PRIVATE_KEY` | Приватный SSH ключ для подключения к VPS | `-----BEGIN OPENSSH PRIVATE KEY-----\n...` |
| `PROJECT_PATH` | Путь к проекту на VPS | `/home/ubuntu/Warehouse_Automation` |

### 3. Генерация SSH ключей (если еще не создавали)

**На VPS сервере:**
```bash
# Генерация SSH ключа для деплоя
ssh-keygen -t rsa -b 4096 -C "github-actions-deploy" -f ~/.ssh/github_deploy

# Добавление публичного ключа в authorized_keys
cat ~/.ssh/github_deploy.pub >> ~/.ssh/authorized_keys

# Показать приватный ключ (скопируйте в GitHub Secret VPS_PRIVATE_KEY)
cat ~/.ssh/github_deploy
```

### 4. Проверка работы

После настройки:

1. **Push в репозиторий** запустит workflow
2. **Tests** выполнятся автоматически
3. При успешных тестах запустится **deploy** на VPS
4. Проверьте статус в **GitHub Actions** вкладке

### 5. Health Check Endpoint

После деплоя система будет доступна по адресам:
- `http://your-server:8000/health` - статус здоровья системы
- `http://your-domain.com/health` - через Nginx proxy

## ✅ Результат

После настройки каждый push в main/master ветку будет:
1. Запускать тесты
2. Проверять качество кода  
3. Автоматически деплоить на VPS
4. Проверять успешность деплоя

**CI/CD готов для "one-click deployment"! 🚀**