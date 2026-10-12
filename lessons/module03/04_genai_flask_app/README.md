# GenAI Flask App: customer inquiry assistant

A Flask web app that triages customer messages with Claude through LangChain. Paste a
message and the app returns a structured analysis:

| Field       | Meaning                                                   |
| ----------- | --------------------------------------------------------- |
| `summary`   | summary of the customer's message                         |
| `sentiment` | 0 (negative) to 100 (positive)                            |
| `category`  | kind of inquiry (billing, technical, general, ...)        |
| `action`    | recommended next step for the support rep                 |

It started as a course app that compared Llama, Granite and Mistral on IBM watsonx. This
version runs on a single Claude model, the same one the playground uses (`claude-sonnet-5-5`).

This is a **self-contained project**. It has its own venv, dependencies, config and tests,
and it shares nothing with the surrounding `langchain-playground` at runtime. You can copy
this folder anywhere and it keeps working.

## Requirements

- Python 3.14.7 (see `.tool-versions`)
- An Anthropic API key

## Setup

Run these from this folder (`lessons/module03/04_genai_flask_app/`):

```bash
make setup      # = make venv install env: .venv with Python 3.14.7, deps, and .env from .env.sample
```

Then put your key in `.env`:

```
ANTHROPIC_API_KEY="sk-ant-..."
```

`make venv` uses the asdf install at `~/.asdf/installs/python/3.14.7`. For another
interpreter, run `make venv PYTHON_BIN=/path/to/python3.14`.

## Run

```bash
make run        # dev server with debugger + auto-reload -> http://127.0.0.1:5000
make serve      # gunicorn, production-style             -> http://127.0.0.1:5000
```

`HOST` and `PORT` can be overridden: `make run PORT=8000`.

Try it from the terminal without the browser (makes one billed API call):

```bash
.venv/bin/flask --app genai_app ask "I was charged twice for my order, please fix it"
```

## Configuration

Everything comes from environment variables, which are also read from this folder's `.env`:

| Variable               | Default             | Notes                                                     |
| ---------------------- | ------------------- | --------------------------------------------------------- |
| `ANTHROPIC_API_KEY`    | (required)          | The app refuses to start without it.                      |
| `ANTHROPIC_MODEL`      | `claude-sonnet-5-5` | Same model as the playground's `app/config/envs.py`.      |
| `ANTHROPIC_MAX_TOKENS` | `2048`              | Claude's adaptive thinking counts against this limit too. |
| `ANTHROPIC_TIMEOUT`    | `60`                | Seconds per API request.                                  |

If replies come back cut off, the app returns a 502 that says to raise
`ANTHROPIC_MAX_TOKENS`.

## API

### `POST /api/generate`

```bash
curl -s localhost:5000/api/generate \
  -H 'Content-Type: application/json' \
  -d '{"message": "My internet has been down since yesterday!"}'
```

```json
{
  "analysis": {
    "summary": "Customer reports an internet outage lasting since yesterday.",
    "sentiment": 15,
    "category": "technical",
    "action": "Check for outages in the customer's area and schedule a technician if none."
  },
  "model": "claude-sonnet-5-5",
  "duration": 2.413
}
```

| Status | When                                                                 |
| ------ | -------------------------------------------------------------------- |
| 400    | body is not a JSON object, `message` is missing or empty, longer than 4000 characters, or extra fields are sent |
| 413    | request body larger than 16 KB                                       |
| 502    | the model reply did not match the schema, or the Anthropic API returned an error |
| 503    | the Anthropic API could not be reached                               |

Every error has the shape `{"error": "..."}`.

### `GET /api/health`

```json
{"status": "ok", "model": "claude-sonnet-5-5"}
```

## Project layout

```
04_genai_flask_app/
├── pyproject.toml             # package metadata, pinned deps, pytest + ruff config
├── Makefile                   # setup / run / serve / test / lint
├── .env.sample                # copy to .env (gitignored)
├── .tool-versions             # python 3.14.7
├── src/genai_app/
│   ├── __init__.py            # create_app(): the application factory
│   ├── config.py              # Config / TestingConfig, read from the environment + .env
│   ├── errors.py              # error handlers: JSON for /api, HTML elsewhere
│   ├── cli.py                 # `flask ask "<message>"`
│   ├── services/
│   │   └── assistant.py       # the LangChain chain: prompt | ChatAnthropic | PydanticOutputParser
│   ├── api/                   # blueprint mounted at /api
│   │   ├── routes.py          # /api/generate, /api/health
│   │   └── schemas.py         # pydantic request/response models
│   ├── web/                   # blueprint for the HTML page
│   │   └── routes.py          # /
│   ├── templates/             # base.html, index.html (Jinja)
│   └── static/                # css/styles.css, js/app.js
└── tests/                     # pytest; the model is faked, no API calls
```

How the pieces fit together:

- **Application factory.** `create_app(config=None, *, chat_model=None)` builds the app.
  `flask --app genai_app` and gunicorn's `"genai_app:create_app()"` both call it. Tests
  call it with `TestingConfig()` and a fake chat model.
- **Service layer.** `InquiryAssistant` holds the LangChain chain and is built once at
  startup. It lives in `app.extensions["assistant"]`, so routes stay thin: validate the
  input, call the service, serialize the result.
- **One schema, two jobs.** `InquiryAnalysis` (pydantic) generates the format
  instructions sent to Claude, and it validates Claude's reply (for example, sentiment
  must be in the 0-100 range). It is also the `analysis` object in the API response.
- **The frontend never injects HTML.** All model output reaches the page through
  `textContent`.

## Tests and lint

```bash
make test         # pytest, with GenericFakeChatModel standing in for Claude: free, offline
make lint         # ruff check --fix + ruff format
make lint-check   # checks only, no writes
```
