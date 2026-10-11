VENV=.venv
PYTHON=$(VENV)/bin/python
PIP=$(VENV)/bin/pip

RUFF=$(VENV)/bin/ruff
PRE_COMMIT=$(VENV)/bin/pre-commit
PIP_REVIEW=$(VENV)/bin/pip-review
CZ=$(VENV)/bin/cz

CONFIG=devtools/pyproject.toml
LESSONS=lessons
REQUIREMENTS=devtools/requirements.txt

.PHONY: venv env install reinstall hooks update-hooks lint lint-check commit check-updates main lesson clean-output

venv:
	@python -m venv $(VENV)

env:
	@test -f .env && echo ".env already exists, leaving it untouched." || cp devtools/.env.sample .env

install:
	@$(PIP) install --upgrade pip && $(PIP) install -r $(REQUIREMENTS)
	@$(MAKE) --no-print-directory hooks

reinstall:
	@$(PIP) install --upgrade pip && $(PIP) install --force-reinstall --no-cache-dir -r $(REQUIREMENTS)
	@$(MAKE) --no-print-directory hooks

hooks:
	@$(PRE_COMMIT) install && $(PRE_COMMIT) install --hook-type commit-msg

update-hooks:
	@$(PRE_COMMIT) autoupdate

lint:
	@$(RUFF) check --fix --config $(CONFIG) .
	@$(RUFF) format --config $(CONFIG) .

lint-check:
	@$(RUFF) check --config $(CONFIG) .
	@$(RUFF) format --check --config $(CONFIG) .

commit:
	@$(CZ) --config $(CONFIG) commit

check-updates:
	@$(PIP_REVIEW)

main:
	@$(PYTHON) main.py

# Remove every output/ folder under lessons/ and the files they hold.
# Rerun a lesson to regenerate just that lesson's output.
clean-output:
	@dirs=$$(find $(LESSONS) -type d -name output -prune 2>/dev/null); \
	if [ -z "$$dirs" ]; then \
		echo "no output folders to remove"; \
	else \
		echo "$$dirs" | while read -r dir; do echo "removing $$dir"; rm -rf "$$dir"; done; \
	fi
