# asdf picks the Python version (.tool-versions) and uv installs the dependencies.
# Handing uv that exact version makes it fail instead of falling back to another
# Python, and rebuild .venv when .tool-versions changes.
export UV_PYTHON := $(shell awk '$$1 == "python" {print $$2}' .tool-versions)

LESSONS=lessons

.PHONY: env install reinstall update check-updates hooks update-hooks lint lint-check commit main lesson clean-output

env:
	@test -f .env && echo ".env already exists, leaving it untouched." || cp devtools/.env.sample .env

# Create .venv if needed and make it match uv.lock exactly.
install:
	@npx skills add guimassoqueto/ai-skills --skill lesson-script -a claude-code -a codex -y
	@uv sync
	@$(MAKE) --no-print-directory hooks

reinstall:
	@rm -rf .venv
	@$(MAKE) --no-print-directory install
	@npx skills update -y

# Upgrade every dependency to its latest version, rewriting uv.lock.
update:
	@uv sync --upgrade

# Show what `make update` would change, without changing anything.
check-updates:
	@uv lock --upgrade --dry-run

hooks:
	@uv run pre-commit install && uv run pre-commit install --hook-type commit-msg

update-hooks:
	@uv run pre-commit autoupdate

lint:
	@uv run ruff check --fix .
	@uv run ruff format .

lint-check:
	@uv run ruff check .
	@uv run ruff format --check .

commit:
	@uv run cz commit

main:
	@uv run main.py

# Run one lesson script from the project root. PYTHONPATH=. lets a script nested
# under lessons/ import app.config.
#   make lesson LESSON=lessons/moduleNN/<nn>_<name>.py
lesson:
	@test -n "$(LESSON)" || { echo "usage: make lesson LESSON=lessons/moduleNN/<nn>_<name>.py"; exit 1; }
	@PYTHONPATH=. uv run $(LESSON)

# Remove every output/ folder under lessons/ and the files they hold.
# Rerun a lesson to regenerate just that lesson's output.
# .venv folders (self-contained projects) are skipped: an installed package may
# ship its own output/ folder.
clean-output:
	@dirs=$$(find $(LESSONS) -name .venv -prune -o -type d -name output -prune -print 2>/dev/null); \
	if [ -z "$$dirs" ]; then \
		echo "no output folders to remove"; \
	else \
		echo "$$dirs" | while read -r dir; do echo "removing $$dir"; rm -rf "$$dir"; done; \
	fi
