---
name: lesson-script
description: Writes and verifies the runnable Python script for a lesson doc in this repo (lessons/moduleNN/NN_name.md in, NN_name.py beside it out). Called with the doc's path; also use it to update or re-run a lesson's script.
---

# Lesson script

Write the runnable script for the lesson doc this skill was called with. The doc is the
spec - no need to ask what to build. Paths are relative to the repo root.

## 1. Find the doc and where its script goes

The doc's path comes with the call, e.g. `lessons/module01/01_similarity_search.md` (the
`lessons/` prefix may be left out). If it is missing, ask for it.

Notes, script and generated files share one stem and live together:

```
lessons/module01/01_similarity_search.md        # notes (the user writes these)
lessons/module01/01_similarity_search.py        # the script (you write this)
lessons/module01/output/01_similarity_search/   # what it generates, if anything (gitignored)
    similarities.csv
    nearest_neighbors.json
```

- The script filename matches the doc filename exactly, `.md` -> `.py`, beside it. A doc
  that has a folder of its own (for its assets) gets its script in that folder.
- Module folders are zero padded: `module01`, never `module1`.
- A new module folder needs no configuration.
- If the script already exists, the doc has likely changed: bring the script in line
  with it rather than starting over.
- A folder that holds its own `pyproject.toml` is a self-contained project, not a lesson
  script. This skill does not apply to it (see `AGENTS.md`).

## 2. Write the script

Read the whole doc, and `app/config/envs.py` for the helpers and model constants that
already exist. Cover the concepts the doc actually describes, in the doc's order, one
short section per concept with a one-line comment introducing it. Flat top-level code:
no `main()`, no argparse, no try/except. These are read as examples, so they should
contain only the code the doc is about.

**Never hardcode a path or a model id.** Import them from `app/config/envs.py`:

| Need                          | Use                                                                       |
| ----------------------------- | ------------------------------------------------------------------------- |
| the doc this script came from | `doc_path(__file__)`                                                      |
| somewhere to write a file     | `output_path(__file__, "similarities.csv")` (parent directory is created) |
| which model                   | its constant in `envs.py` (see below)                                     |
| an LLM's reply limit          | `DEFAULT_MAX_TOKENS`                                                      |

Both path helpers derive everything from `__file__`, so renaming or moving a lesson
needs no edit anywhere.

Where results go:

- text, or anything you would just look at -> `print("[section label]", ...)`
- file shaped (`.json`, `.csv`, `.md`, ...) -> write through `output_path(...)`

## 3. Add what the lesson needs

- **A model.** The first lesson that needs a model (an LLM, an embedding model, ...)
  adds its id to `app/config/envs.py` as a constant, with a one-line comment saying
  which lessons use it. Model ids move faster than training data, so an unfamiliar id
  there is more likely new than wrong: keep it, don't swap in one you recognise.
- **An API key.** Keys load themselves: importing `app.config.envs` runs
  `load_dotenv()`. A lesson that needs an API key adds the variable, empty, to
  `devtools/.env.sample`, and the user puts the value in `.env`. Clients that read
  their key from the environment (`ChatAnthropic` and `ANTHROPIC_API_KEY`, say) then
  need no argument.
- **A package.** `uv add --raw <package>` records it, unpinned, in `pyproject.toml` and
  `uv.lock`, and installs it (without `--raw`, uv writes a `>=` bound).

## 4. Verify without spending the user's money

Lint and format just the script, and fix whatever ruff reports but cannot fix itself.
Don't use `make lint` here: it covers the whole repo, not just this script.

```bash
uv run ruff check --fix lessons/moduleNN/<nn>_<name>.py
uv run ruff format lessons/moduleNN/<nn>_<name>.py
```

**No billed calls:** run it with `make lesson LESSON=lessons/moduleNN/<nn>_<name>.py`
(it sets `PYTHONPATH=.`, which nested scripts need) and check what it prints and writes.

**A paid API** (Claude, say): every run makes real billed calls. **Ask before running
one for real.** Verify it for free first by stubbing the model and running the script
unchanged from a scratchpad file (a temp directory outside the repo) - this exercises
the prompts, parsers and file writes. For a LangChain chat model:

```python
import runpy

import langchain_anthropic
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

# one AIMessage per model call the script makes, in order
canned = iter([AIMessage("..."), AIMessage('{"key": "value"}'), AIMessage("a, b, c")])
langchain_anthropic.ChatAnthropic = lambda **kwargs: GenericFakeChatModel(messages=canned)
runpy.run_path("lessons/moduleNN/<nn>_<name>.py", run_name="__main__")
```

Give one canned `AIMessage` per model call, in order, each shaped for whatever parser
consumes it. A paid embedding model is stubbed the same way, with
`lambda **kwargs: DeterministicFakeEmbedding(size=...)` (from `langchain_core.embeddings`)
in place of its class. Run the file from the repo root with
`PYTHONPATH=. uv run <file>`. Afterwards delete the stub output or restore the
real files, so `output/` only ever holds genuine runs.

## 5. Report

Give the script's path and the command that runs it, what it printed and wrote, what you
added to `envs.py`, `devtools/.env.sample` or `pyproject.toml`, and whether it
ran for real or against stubs. After a stubbed run, offer the real one.
