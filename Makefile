# =============================================================================
# Aegis — Makefile
# =============================================================================

COMPOSE := docker compose
COMPOSE_PROD := docker compose -f docker-compose.yml -f docker-compose.prod.yml

.PHONY: dev prod down backup logs health migrate test lint format clean

# --- Development ---
dev:
	$(COMPOSE) up -d
	@echo "Services starting... run 'make health' to check status"

# --- Production ---
prod:
	./infrastructure/scripts/deploy.sh --prod

# --- Stop all services ---
down:
	$(COMPOSE) down

# --- Backup ---
backup:
	./infrastructure/scripts/backup.sh

# --- Logs ---
logs:
	$(COMPOSE) logs -f

# --- Health check ---
health:
	@echo "=== Service Health ==="
	@$(COMPOSE) ps
	@echo ""
	@echo "=== PostgreSQL ==="
	@$(COMPOSE) exec postgres pg_isready -U aegis || echo "UNHEALTHY"
	@echo ""
	@echo "=== Redis ==="
	@$(COMPOSE) exec redis redis-cli -a "$${REDIS_PASSWORD}" ping || echo "UNHEALTHY"
	@echo ""
	@echo "=== Qdrant ==="
	@$(COMPOSE) exec qdrant wget -qO- http://localhost:6333/healthz || echo "UNHEALTHY"

# --- Database migrations ---
migrate:
	cd backend && uv run alembic upgrade head

# --- Run tests ---
test:
	cd backend && uv run pytest tests/ -v --cov=app --cov-report=term-missing --cov-fail-under=80

# --- Lint ---
lint:
	cd backend && uv run ruff check .
	@if [ -d console/node_modules ]; then cd console && npx biome check .; fi

# --- Format ---
format:
	cd backend && uv run ruff format .
	@if [ -d console/node_modules ]; then cd console && npx biome format --write .; fi

# --- Clean ---
clean:
	$(COMPOSE) down -v
	rm -rf backend/.venv console/.next console/node_modules mobile/node_modules
