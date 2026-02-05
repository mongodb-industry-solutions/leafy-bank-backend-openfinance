build:
	docker-compose up --build -d

start: 
	docker-compose start

stop:
	docker-compose stop

clean:
	docker-compose down --rmi all -v

install_poetry:
	brew install pipx
	pipx ensurepath
	pipx install poetry==1.8.4

poetry_start:
	cd backend && poetry config virtualenvs.in-project true

poetry_install:
	cd backend && poetry install --no-interaction -v --no-cache --no-root

poetry_update:
	cd backend && poetry update

# Local development commands
dev:
	cd backend && poetry run uvicorn main:app --reload --host 0.0.0.0 --port 8003 --log-level debug

run:
	cd backend && poetry run uvicorn main:app --host 0.0.0.0 --port 8003

run-verbose:
	cd backend && poetry run uvicorn main:app --host 0.0.0.0 --port 8003 --log-level debug

logs:
	cd backend && poetry run uvicorn main:app --reload --host 0.0.0.0 --port 8003 --log-level trace

# Quick setup (first time)
setup: poetry_start poetry_install

# Check if backend can import correctly
check:
	cd backend && poetry run python -c "from main import app; print('✓ App loads successfully')"