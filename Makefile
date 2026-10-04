.PHONY: install test run up down check
install:
	python -m venv .venv && . .venv/bin/activate && pip install -r engine/requirements.txt
test:
	cd engine && python -m pytest -q
run:
	cd engine && uvicorn app.main:app --reload --port 8000
up:
	docker compose up -d --build
down:
	docker compose down
check:
	./scripts/gtm.sh health
