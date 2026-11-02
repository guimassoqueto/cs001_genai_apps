# cs001_genai_apps

Develop Generative AI Applications. The user writes course notes under `lessons/`; the
`lesson-script` skill writes the runnable script for each. If you can't load skills
and are asked for it, read `.agents/skills/lesson-script/SKILL.md` and follow it.

`lessons/module02/01_langchain_core_concepts.py` is the reference lesson script: match
its shape.

## Self-contained projects

A folder under `lessons/` with its own `pyproject.toml` (`lessons/module03/04_genai_flask_app/`)
is an independent project, not a lesson, so the skill doesn't apply. Follow its own
README and Makefile, use its own `.venv`, never import `app.config` from it or add its
dependencies to the root `pyproject.toml`, and add it to `extend-exclude` there.

## LangChain 1.x details that are easy to get wrong

The lessons call Claude through `ChatAnthropic(model=DEFAULT_MODEL, max_tokens=DEFAULT_MAX_TOKENS)`,
which reads `ANTHROPIC_API_KEY` from `.env`, so every real run is billed.

- `message.text` is a **property**, not a method: `response.text`, never `response.text()`.
- Current Claude models run adaptive thinking by default, so `response.content`
  is a list of content blocks rather than a string. `.text` and the output parsers
  extract the text correctly, so no special handling is needed. But thinking tokens
  count against `max_tokens`: if `DEFAULT_MAX_TOKENS` is tight, a reply can be cut
  off before the answer starts, which surfaces as an output-parser exception on
  truncated JSON rather than as an obvious truncation. Raise it, don't work around it.
- To confirm an unfamiliar `DEFAULT_MODEL`, use `client.models.retrieve("<id>")` or
  `client.models.list()` (metadata only, no tokens billed) instead of replacing it
  with an id you recognise.
- Pass `{format_instructions}` in through `.partial(...)`. The JSON schema it
  returns contains braces, which must not be re-parsed as template variables.
- `LengthBasedExampleSelector(max_length=...)` counts words. Tune it so selection
  is visibly partial (2 of 4, say); "1 of 4" reads like a bug to a learner.

## Conventions

- Python 3.14 from asdf (`.tool-versions`). uv manages `.venv`: add dependencies unpinned
  with `uv add --raw <pkg>` (plus `--dev` for tooling), run tools with `uv run`. Never
  `pip install`: `.venv` has no pip, so it would hit asdf's global Python.
- `make lint` / `make lint-check`: ruff fix / check only (line length 120, config in
  `pyproject.toml`).
- Don't commit unless asked. A commit-msg hook enforces conventional commits (`feat:`,
  `fix:`, `chore:`, ...); `make commit` runs commitizen.
- `output/` is gitignored: never commit generated files. `make clean-output` deletes them.
- Use `git mv` when moving tracked files.
- `README.md` is the human-facing doc; update it when the architecture changes.
- Skills live in `.agents/skills/<name>/`, so edit them there. `.claude/skills/<name>` is
  a relative symlink to each, for Claude Code.
