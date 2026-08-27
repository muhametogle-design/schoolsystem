.PHONY: install test seed db-up run demo

install:
	python3 -m venv .venv
	. .venv/bin/activate && pip install -r requirements-dev.txt

test:
	. .venv/bin/activate && pytest

seed:
	. .venv/bin/activate && python scripts/seed_data.py

db-up:
	docker compose up -d db

run:
	. .venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 5000

demo:
	. .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 5000
