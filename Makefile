PYTHON ?= python3
BIN := .venv/bin
.PHONY: setup run test test-integration lint format migrate migration db-up down
setup:
	$(PYTHON) -m venv .venv
	$(BIN)/python -m pip install -r requirements-dev.lock
	$(BIN)/python -m pip install --no-deps -e .
run:
	$(BIN)/uvicorn enterprise_knowledge_engine.main:create_app --factory --reload --no-access-log
test:
	$(BIN)/pytest -m 'not integration'
test-integration:
	$(BIN)/pytest -m integration
lint:
	$(BIN)/ruff check .
	$(BIN)/ruff format --check .
format:
	$(BIN)/ruff check --fix .
	$(BIN)/ruff format .
migrate:
	$(BIN)/alembic upgrade head
migration:
	$(BIN)/alembic revision --autogenerate -m "$(message)"
db-up:
	docker compose up -d db
down:
	docker compose down

.PHONY: demo
demo:
	$(BIN)/python scripts/demo_ingestion.py

.PHONY: demo-search
demo-search:
	$(BIN)/python scripts/demo_search.py

.PHONY: demo-qa
demo-qa:
	$(BIN)/python scripts/demo_qa.py

.PHONY: mcp demo-mcp
mcp:
	$(BIN)/python -m enterprise_knowledge_engine.mcp
demo-mcp:
	$(BIN)/python scripts/demo_mcp.py

.PHONY: evaluate evaluate-validate performance-demo audit
evaluate:
	$(BIN)/python -m enterprise_knowledge_engine.evaluation.runner
evaluate-validate:
	$(BIN)/python -m enterprise_knowledge_engine.evaluation.runner --validate-only
performance-demo:
	$(BIN)/python scripts/demo_performance.py
audit:
	$(BIN)/python scripts/check_secrets.py
	$(BIN)/pip-audit -r requirements-dev.lock --disable-pip --no-deps --progress-spinner off

.PHONY: demo-portfolio
demo-portfolio:
	bash demo/demo_requests.sh

.PHONY: frontend-setup frontend-dev frontend-check frontend-build demo-frontend
frontend-setup:
	cd frontend && npm ci
frontend-dev:
	cd frontend && npm run dev
frontend-check:
	cd frontend && npm run typecheck && npm run lint && npm run format:check && npm test
frontend-build:
	cd frontend && npm run build && npm run check:client
demo-frontend:
	$(BIN)/python scripts/demo_frontend.py
