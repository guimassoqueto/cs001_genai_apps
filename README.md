# langchain-playground

Scratch repo for working through a LangChain course, using Claude as the model provider.

## Requirements

- Python 3.14.7 (see `.tool-versions`)
- An Anthropic API key

## Setup

```bash
make venv       # create .venv
make env        # copy devtools/.env.sample to .env (won't overwrite an existing one)
make install    # install dependencies and the git hooks
```

Then put your key in `.env`:

```
ANTHROPIC_API_KEY="sk-ant-..."
```

## Usage

| Command              | Does                                                        |
| -------------------- | ----------------------------------------------------------- |
| `make main`          | Run `main.py`                                               |
| `make lesson LESSON=<path>` | Run one lesson script                         |
| `make clean-output`  | Delete every generated `output/` folder under `lessons/`    |
| `make lint`          | Lint and format, applying fixes                             |
| `make lint-check`    | Lint and format checks only, no writes                      |
| `make commit`        | Commit through commitizen (conventional commit messages)    |
| `make hooks`         | (Re)install the pre-commit and commit-msg hooks             |
| `make update-hooks`  | Bump the pinned hook revisions in `.pre-commit-config.yaml` |
| `make check-updates` | List outdated dependencies                                  |
| `make reinstall`     | Force a clean reinstall of all dependencies                 |

## Layout

```
lessons/             # the course: notes, scripts and generated files, by module
app/config/envs.py   # API key, model defaults, notes/output path mapping
main.py              # entry point
devtools/            # requirements, tool config (ruff, commitizen), .env.sample
```

## Lessons

Each lesson keeps its notes, its script and its results together:

```
lessons/
  module02/
    01_langchain_core_concepts.md      # the notes
    01_langchain_core_concepts.py      # the LangChain script written from them
    output/
      01_langchain_core_concepts/      # whatever that script generates
        concepts.json
        message_types.csv
```

The notes and the script share a name, so they sit side by side in the file tree
and one fuzzy-find turns up both. Generated files stay in the module you are
reading, under `output/` (gitignored - rerun the lesson to recreate them).

Module folders are zero padded (`module02`, not `module2`) so they keep sorting
correctly past module 9.

Run a lesson with:

```bash
make lesson LESSON=lessons/module02/01_langchain_core_concepts.py
```

## Adding a lesson

Drop the notes in `lessons/moduleNN/<nn>_<name>.md`. Nothing else needs wiring:
a script written beside it finds its own notes and output directory through
`app/config/envs.py`:

- `doc_path(__file__)` -> the `.md` next to the script
- `output_path(__file__, "concepts.json")` -> where to write a generated file,
  with the directory already created

So a lesson script holds only LangChain code - no paths, no model ids. Results
that are just text go to the terminal; anything file-shaped (`.json`, `.csv`,
`.md`, ...) goes under `output/`.

Tool configuration lives in `devtools/pyproject.toml`; every command that needs it
passes `--config devtools/pyproject.toml`.

`CLAUDE.md` holds the instructions Claude Code loads automatically in a new
session: the layout contract, how a lesson script is written, and how to verify
one without making billed API calls.
