run:
	python3 -B main.py

setup:
	pip install -r requirements.txt

env:
	python3 -m venv venv

revision:
	alembic revision --autogenerate -m "$(m)"

upgrade:
	alembic upgrade head

downgrade:
	alembic downgrade "$(r)"

start:
	uvicorn main:app --reload

poetry-start:
	@echo "PORT is $$PORT"
	poetry run uvicorn main:app --host 0.0.0.0 --port 8080
	@echo "Starting Pluto AI API from makefile"
