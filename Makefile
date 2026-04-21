.PHONY: install dev db-up db-down seed api dashboard simulate test fmt lint

install:
	pip install -e ".[dev]"
	cd monday-webhook && npm install

db-up:
	docker compose up -d db

db-down:
	docker compose down

seed:
	python scripts/seed_kb.py

api:
	uvicorn supportops.api.main:app --reload --host 0.0.0.0 --port 8000

dashboard:
	streamlit run supportops/dashboard/app.py

simulate:
	python scripts/run_simulation.py --tickets 1000 --duration 60

test:
	pytest -q

fmt:
	ruff format .

lint:
	ruff check .
