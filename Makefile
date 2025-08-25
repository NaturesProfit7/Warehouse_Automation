.PHONY: help install install-dev test lint format typecheck clean dev build up down logs

help:		## Show this help
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install:	## Install production dependencies
	pip install -r requirements.txt

install-dev:	## Install development dependencies
	pip install -r requirements-dev.txt

test:		## Run tests
	pytest tests/ -v

test-coverage:	## Run tests with coverage
	pytest tests/ -v --cov=src --cov-report=html --cov-report=term

lint:		## Run code linting
	ruff check src/ tests/
	black --check src/ tests/

format:		## Format code
	ruff check --fix src/ tests/
	black src/ tests/

typecheck:	## Run type checking
	mypy src/

clean:		## Clean up temporary files
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf htmlcov/
	rm -rf dist/
	rm -rf build/

dev:		## Start development environment
	docker-compose -f docker-compose.dev.yml up -d

dev-logs:	## Show development logs
	docker-compose -f docker-compose.dev.yml logs -f

dev-down:	## Stop development environment
	docker-compose -f docker-compose.dev.yml down

build:		## Build Docker images
	docker-compose build

up:		## Start production environment
	docker-compose up -d

down:		## Stop all services
	docker-compose down

logs:		## Show logs
	docker-compose logs -f

status:		## Show container status
	docker-compose ps

shell:		## Open shell in webhook container
	docker-compose exec webhook bash

redis-cli:	## Open Redis CLI
	docker-compose exec redis redis-cli

backup-sheets:	## Create backup of Google Sheets data
	python scripts/backup.py

migrate:	## Run data migrations
	python scripts/migrate.py

init-sheets:	## Initialize Google Sheets structure
	python scripts/init_sheets.py

# Pre-commit hooks
pre-commit:	## Install pre-commit hooks
	pre-commit install

pre-commit-run:	## Run pre-commit on all files
	pre-commit run --all-files