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
