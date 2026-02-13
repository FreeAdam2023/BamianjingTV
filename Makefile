.PHONY: help install dev test lint clean docker-build docker-up docker-down frontend-install frontend-dev ue5-deploy ue5-status ue5-stop ue5-logs

# Default target
help:
	@echo "Hardcore Player - Learning Video Factory"
	@echo ""
	@echo "Development:"
	@echo "  make install         Install backend dependencies"
	@echo "  make dev             Run backend dev server"
	@echo "  make frontend-install Install frontend dependencies"
	@echo "  make frontend-dev    Run frontend dev server"
	@echo "  make dev-all         Run both backend and frontend"
	@echo "  make test            Run tests"
	@echo "  make lint            Run linter"
	@echo "  make clean           Clean cache files"
	@echo ""
	@echo "Docker (Production with GPU):"
	@echo "  make docker-build    Build Docker images"
	@echo "  make docker-up       Start API + Frontend (requires NVIDIA GPU)"
	@echo "  make docker-down     Stop all services"
	@echo "  make docker-logs     View logs"
	@echo ""
	@echo "Docker (Production - CPU only):"
	@echo "  make docker-cpu-up   Start API + Frontend (no GPU required)"
	@echo "  make docker-cpu-down Stop CPU services"
	@echo ""
	@echo "Docker (Development - CPU only):"
	@echo "  make docker-dev      Start dev environment with hot reload"
	@echo ""

# ============ Backend ============

install:
	cd backend && pip install -r requirements.txt

dev:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

test:
	cd backend && pytest tests/ -v

lint:
	cd backend && ruff check app/ tests/
	cd backend && ruff format --check app/ tests/

format:
	cd backend && ruff format app/ tests/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	find . -type d -name ".next" -exec rm -rf {} +

# ============ Frontend ============

frontend-install:
	cd frontend && pnpm install

frontend-dev:
	cd frontend && pnpm dev

frontend-build:
	cd frontend && pnpm build

# Run both backend and frontend
dev-all:
	@echo "Starting backend on :8001 and frontend on :3001"
	@make dev & make frontend-dev

# ============ Docker (Production) ============

docker-build:
	docker compose build

docker-up:
	docker compose up -d api frontend

docker-up-all:
	docker compose --profile automation up -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f

docker-logs-api:
	docker compose logs -f api

docker-logs-frontend:
	docker compose logs -f frontend

# ============ Docker (Production - CPU) ============

docker-cpu-up:
	docker compose -f docker-compose.cpu.yml up -d api frontend

docker-cpu-up-all:
	docker compose -f docker-compose.cpu.yml --profile automation up -d

docker-cpu-down:
	docker compose -f docker-compose.cpu.yml down

docker-cpu-logs:
	docker compose -f docker-compose.cpu.yml logs -f

# ============ Docker (Development) ============

docker-dev:
	docker compose -f docker-compose.dev.yml up --build

docker-dev-down:
	docker compose -f docker-compose.dev.yml down

# ============ UE5 Virtual Studio ============

ue5-deploy:
	bash deploy/deploy-ue5.sh --skip-package

ue5-deploy-full:
	bash deploy/deploy-ue5.sh

ue5-status:
	systemctl status virtual-studio

ue5-stop:
	sudo systemctl stop virtual-studio

ue5-logs:
	sudo journalctl -u virtual-studio -f

# ============ Utilities ============

docs:
	@echo "API documentation: http://localhost:8000/docs"
	@open http://localhost:8000/docs 2>/dev/null || xdg-open http://localhost:8000/docs 2>/dev/null || echo "Open http://localhost:8000/docs"

app:
	@echo "Frontend: http://localhost:3001"
	@open http://localhost:3001 2>/dev/null || xdg-open http://localhost:3001 2>/dev/null || echo "Open http://localhost:3001"
