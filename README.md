# CS001: Develop Generative AI Applications: Get Started

Certificate available at: https://www.coursera.org/account/accomplishments/verify/6T5XGQAXSARH

## Requirements

- [asdf](https://asdf-vm.com) with the `python` and `uv` plugins. `.tool-versions` pins
  Python 3.14.7 and uv; `asdf install` installs both.
- [npx skills](https://github.com/vercel-labs/skills) to load the required project skills
- An Anthropic API key: the lessons call Claude

asdf provides Python and uv; uv installs the dependencies into `.venv` with that Python
and never downloads one of its own (`python-preference = "only-system"` in
`pyproject.toml`). To change Python, edit `.tool-versions` and run `asdf install`: the
Makefile hands uv that version, so `make install` rebuilds `.venv` with it.

## Setup

```bash
make env        # copy devtools/.env.sample to .env (won't overwrite an existing one)
make install    # create .venv with the locked dependencies, install the git hooks and the ai skills
```

Then put your key in `.env`:

```
ANTHROPIC_API_KEY="sk-ant-..."
```

Dependencies are declared unpinned in `pyproject.toml` (tooling in the `dev` group) and
locked to exact versions in `uv.lock`. `uv add --raw <package>` (plus `--dev` for
tooling) records a new one in both and installs it; `--raw` keeps it unpinned, where
plain `uv add` would write a `>=` bound. `uv remove <package>` takes it out. `.venv` has
no pip, so a `pip install` would land in asdf's global Python. torch comes from
PyTorch's CPU-only index (`[tool.uv.sources]`) while it is a direct dependency, so when
a package pulls it in, add `torch` too.

When a lesson needs another API key, it is listed in `devtools/.env.sample`: put its
value in `.env`.

On commit, the pre-commit hook fixes the staged files (trailing whitespace, final
newline, `ruff check --fix`, `ruff format`) and re-stages the fixes, so the commit only
fails on issues that cannot be fixed automatically. A file with extra unstaged edits is
not re-staged (that would clash with pre-commit's stash): stage the whole file and
commit again. The commit message must be a conventional commit (`feat: ...`,
`chore: ...`) with a header of at most 72 characters.

## Usage

| Command                     | Does                                                        |
| --------------------------- | ----------------------------------------------------------- |
| `make main`                 | Run `main.py`                                               |
| `make lesson LESSON=<path>` | Run one lesson script                                       |
| `make clean-output`         | Delete every generated `output/` folder under `lessons/`    |
| `make lint`                 | Lint and format, applying fixes                             |
| `make lint-check`           | Lint and format checks only, no writes                      |
| `make commit`               | Commit through commitizen (conventional commit messages)    |
| `make hooks`                | (Re)install the pre-commit and commit-msg hooks             |
| `make update-hooks`         | Bump the pinned hook revisions in `.pre-commit-config.yaml` |
| `make check-updates`        | List what `make update` would upgrade, changing nothing     |
| `make update`               | Upgrade all dependencies to their latest versions           |
| `make reinstall`            | Delete `.venv` and run `make install` again                 |

## Layout

```
lessons/             # the course: notes, scripts and generated files, by module
app/config/envs.py   # API key, model settings, notes/output path mapping
main.py              # entry point: checks the API key loads
pyproject.toml       # dependencies and tool config (uv, ruff, commitizen)
uv.lock              # exact dependency versions, written by uv
devtools/            # .env.sample, pre-commit fixer script
.agents/skills/      # agent skills (lesson-script)
.claude/skills/      # symlinks to .agents/skills, for Claude Code
```

## Lessons

Each lesson keeps its notes, its script and its results together. Module folders are
zero padded (`module02`, not `module2`) so they keep sorting past module 9.

```
lessons/
  module02/
    01_langchain_core_concepts.md      # the notes (you write these)
    01_langchain_core_concepts.py      # the script (the lesson-script skill writes it)
    output/
      01_langchain_core_concepts/       # what the script generates (gitignored)
        concepts.json
        message_types.csv
```

Write the notes, then call the skill with their path:

```
/lesson-script lessons/module02/01_langchain_core_concepts.md    # Claude Code, Cursor, Copilot
$lesson-script lessons/module02/01_langchain_core_concepts.md    # Codex
```

The script finds its notes and output folder through `app/config/envs.py`, so it holds
no paths or model ids. Run it with:

```bash
make lesson LESSON=lessons/module02/01_langchain_core_concepts.py
```

Every run makes real calls to Claude, billed to the key in `.env`.

## Self-contained projects

Some lessons are full apps instead of single scripts, e.g.
`lessons/module03/04_genai_flask_app/`. Each one has its own venv, `pyproject.toml`,
`Makefile`, `.env` and README, and it does not use the root `.venv` or `app/config`.
Set it up and run it from inside its own folder. Add the folder to `extend-exclude` in
the root `pyproject.toml`, because each project lints itself.

## Agents

`AGENTS.md` holds the always-loaded instructions for coding agents; `CLAUDE.md` only
imports it (`@AGENTS.md`), so edit `AGENTS.md`. Skills use the
[Agent Skills](https://agentskills.io) format in `.agents/skills/<name>/`, read by
Codex, Cursor and Copilot. Claude Code reads `.claude/skills/` instead, so each skill
gets a symlink there:

```bash
ln -s ../../.agents/skills/<name> .claude/skills/<name>
```
