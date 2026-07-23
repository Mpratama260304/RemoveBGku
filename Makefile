.PHONY: install dev preview test lint format migrate superuser bootstrap-admin docker-build docker-up docker-down logs doctor cleanup smoke-test
install:
	python -m pip install -r requirements-dev.txt
dev:
	python manage.py runserver
preview:
	DEBUG=false python manage.py runserver --insecure
test:
	pytest
lint:
	ruff check . && ruff format --check .
format:
	ruff check --fix . && ruff format .
migrate:
	python manage.py migrate
superuser:
	python manage.py createsuperuser
bootstrap-admin:
	python manage.py bootstrap_admin
docker-build:
	docker build -t removebgku:local .
docker-up:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
docker-down:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml down
logs:
	docker compose logs -f --tail=100 web worker
doctor:
	python manage.py doctor
cleanup:
	python manage.py cleanup_expired_jobs
smoke-test:
	./scripts/smoke-test.sh
