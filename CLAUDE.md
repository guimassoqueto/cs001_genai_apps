# cs001_genai_apps

Develop Generative AI Applications. The user writes course notes;

## The standing task

When the user points at a doc under `lessons/` ("do `module03/02_chains.md`",
"here is a new doc"), read it and write the LangChain script for it. The doc is
the spec - no need to ask what to build.

`lessons/module02/01_langchain_core_concepts.py` is the reference implementation.
Match its shape.

## Layout contract

Notes, script and generated files share one stem and live together:

```
lessons/module02/01_langchain_core_concepts.md        # notes (the user writes these)
lessons/module02/01_langchain_core_concepts.py        # the script (you write this)
lessons/module02/output/01_langchain_core_concepts/   # what it generates (gitignored)
    concepts.json
    message_types.csv
```

- The script filename matches the doc filename exactly, `.md` -> `.py`, beside it.
- Module folders are zero padded: `module02`, never `module2`.
- A new module folder needs no configuration.

### Self-contained projects

A folder under `lessons/` that holds its own `pyproject.toml` (e.g.
`lessons/module03/04_genai_flask_app/`) is an independent project, not a lesson
script. The rules above and below do not apply to it. Follow its own README and
Makefile, use its own `.venv`, and never import `app.config` from it or add its
dependencies to `devtools/requirements.txt`. Add each one to `extend-exclude` in
`devtools/pyproject.toml`.

## Writing a lesson script

Cover the concepts the doc actually describes, in the doc's order, one short
section per concept with a one-line comment introducing it. Flat top-level code:
no `main()`, no argparse, no try/except. These are read as examples, so they
should contain only the LangChain code the doc is about.

**Never hardcode a path or a model id.** Import them from `app/config/envs.py`:

| Need                          | Use                                                                   |
| ----------------------------- | --------------------------------------------------------------------- |
| the doc this script came from | `doc_path(__file__)`                                                  |
| somewhere to write a file     | `output_path(__file__, "concepts.json")` (parent directory is created) |
| which model                   | `DEFAULT_MODEL`, `DEFAULT_MAX_TOKENS`                                 |

Both path helpers derive everything from `__file__`, so renaming or moving a
lesson needs no edit anywhere.

Where results go:

- text, or anything you would just look at -> `print("[section label]", ...)`
- file shaped (`.json`, `.csv`, `.md`, ...) -> write through `output_path(...)`

The key loads itself: importing `app.config.envs` runs `load_dotenv()`, after
which `ChatAnthropic(model=DEFAULT_MODEL, max_tokens=DEFAULT_MAX_TOKENS)` finds
`ANTHROPIC_API_KEY` with no argument.

## Verify without spending the user's money

Running a lesson makes real billed API calls. **Ask before running one for real.**
Verify for free first by stubbing the model and running the script unchanged from
a scratchpad file - this exercises the prompts, selectors, parsers and file writes:

```python
import runpy

import langchain_anthropic
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

# one AIMessage per model call the script makes, in order
canned = iter([AIMessage("..."), AIMessage('{"key": "value"}'), AIMessage("a, b, c")])
langchain_anthropic.ChatAnthropic = lambda **kwargs: GenericFakeChatModel(messages=canned)
runpy.run_path("lessons/module02/01_langchain_core_concepts.py", run_name="__main__")
```

Give one canned `AIMessage` per model call, in order, each shaped for whatever
parser consumes it. Run it with `PYTHONPATH=.`. Afterwards delete the stub output
or restore the real files, so `output/` only ever holds genuine runs.

## LangChain 1.x details that are easy to get wrong

- `message.text` is a **property**, not a method: `response.text`, never `response.text()`.
- Current Claude models run adaptive thinking by default, so `response.content`
  is a list of content blocks rather than a string. `.text` and the output parsers
  extract the text correctly, so no special handling is needed. But thinking tokens
  count against `max_tokens`: if `DEFAULT_MAX_TOKENS` is tight, a reply can be cut
  off before the answer starts, which surfaces as an output-parser exception on
  truncated JSON rather than as an obvious truncation. Raise it, don't work around it.
- Model ids move faster than training data, so an unfamiliar `DEFAULT_MODEL` is
  more likely new than wrong. Confirm with `client.models.retrieve("<id>")` or
  `client.models.list()` (metadata only, no tokens billed) instead of replacing it
  with an id you recognise.
- Pass `{format_instructions}` in through `.partial(...)`. The JSON schema it
  returns contains braces, which must not be re-parsed as template variables.
- `LengthBasedExampleSelector(max_length=...)` counts words. Tune it so selection
  is visibly partial (2 of 4, say); "1 of 4" reads like a bug to a learner.

## Commands

| Command                                                            | Does                                                                   |
| ------------------------------------------------------------------ | ---------------------------------------------------------------------- |
| `make lesson LESSON=lessons/module02/01_langchain_core_concepts.py` | run one lesson (sets `PYTHONPATH=.`, which nested scripts need)        |
| `make lint` / `make lint-check`                                    | ruff fix / check only; line length 120, config `devtools/pyproject.toml` |
| `make clean-output`                                                | delete every `lessons/**/output/` folder                               |
| `make commit`                                                      | commit through commitizen                                              |

## Repo conventions

- Do not commit unless asked. A commit-msg hook enforces conventional commits
  (`feat:`, `fix:`, `chore:`, ...).
- `output/` is gitignored. Never commit generated files.
- Use `git mv` when moving tracked files.
- Python 3.14, venv at `.venv`, dependencies unpinned in `devtools/requirements.txt`.
- `README.md` is the human-facing doc; update it when the architecture changes.
