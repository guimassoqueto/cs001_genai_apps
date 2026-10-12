VENV=.venv
PYTHON=$(VENV)/bin/python
PIP=$(VENV)/bin/pip
FLASK=$(VENV)/bin/flask
GUNICORN=$(VENV)/bin/gunicorn
PYTEST=$(VENV)/bin/pytest
RUFF=$(VENV)/bin/ruff

# Python 3.14.7 from .tool-versions (asdf). Override with: make venv PYTHON_BIN=/path/to/python3.14
PYTHON_BIN ?= $(HOME)/.asdf/installs/python/3.14.7/bin/python3.14

APP=genai_app
HOST ?= 127.0.0.1
PORT ?= 5000

.PHONY: venv env install setup run serve test lint lint-check clean

venv:
	@$(PYTHON_BIN) -m venv $(VENV)

env:
	@test -f .env && echo ".env already exists, leaving it untouched." || cp .env.sample .env

install:
	@$(PIP) install --upgrade pip && $(PIP) install -e ".[dev]"

# venv + dependencies + .env in one go
setup: venv install env

# Development server with the debugger and auto-reload
run:
	@$(FLASK) --app $(APP) run --debug --host $(HOST) --port $(PORT)

# Production-style WSGI server. Threads keep a worker free while it waits on slow model calls.
serve:
	@$(GUNICORN) --workers 2 --threads 4 --timeout 180 --bind $(HOST):$(PORT) "$(APP):create_app()"

test:
	@$(PYTEST)

lint:
	@$(RUFF) check --fix .
	@$(RUFF) format .

lint-check:
	@$(RUFF) check .
	@$(RUFF) format --check .

clean:
	@rm -rf .pytest_cache .ruff_cache src/*.egg-info
	@find . -path ./$(VENV) -prune -o -type d -name __pycache__ -exec rm -rf {} +
