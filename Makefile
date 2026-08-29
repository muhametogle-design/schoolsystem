.PHONY: install dev test seed docker psql clean

install:
	pip install -r requirements-dev.txt

dev: ## Run the API + dashboard locally on SQLite demo tier (http://localhost:8000)
	python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

seed:
	python scripts/seed_data.py

test:
	python -m pytest -q

docker: ## Full stack on real PostgreSQL 16
	docker compose up --build

psql:
	docker compose exec db psql -U school -d schoolsystem

clean:
	rm -rf data/*.db* tests/_test_schoolsystem.db .pytest_cache
