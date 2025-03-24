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
	poetry run uvicorn main:app --host 0.0.0.0 --port 10000
	@echo "Starting Pluto AI API from makefile"

docker-build:
	docker build -t pluto-ai .

docker-run:
	docker run -p 10000:10000 pluto-ai

docker-stop:
	docker stop pluto-ai

docker-remove:
	docker rm pluto-ai
