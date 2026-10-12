# GenAI Flask App: customer inquiry assistant

A Flask web app that triages customer messages with Claude through LangChain. Paste a
message and the app returns a structured analysis:

| Field       | Meaning                                                   |
| ----------- | --------------------------------------------------------- |
| `summary`   | summary of the customer's message                         |
| `sentiment` | 0 (negative) to 100 (positive)                            |
| `category`  | kind of inquiry (billing, technical, general, ...)        |
| `action`    | recommended next step for the support rep                 |

Features:

- **Four Claude models:** Opus 5.5, Fable 5.1, Sonnet 5.5 (the default) and Haiku 5.5.
  Pick one per message.
- **Streaming or complete answers:** with **Stream** on, each answer is filled in token
  by token as the model writes it. Switch it off to get the whole answer at once. This
  works for one model and for A/B tests.
- **A/B testing:** switch it on, pick two or more models, and each message goes to all of
  them in parallel. The answers appear side by side. Vote for the best one, and the
  **A/B results** panel keeps win rates, latency and token use per model.
- **Conversation memory:** follow-up messages are analyzed with the earlier ones as
  context. **Clear Chat** starts a fresh conversation.
- **Response caching:** asking the same thing in the same context again is answered from
  the cache, with no API call.
- **Error handling and logging:** every error has a clear code and message, every request
  has an id, and every model call is logged.

It started as a course app that compared Llama, Granite and Mistral on IBM watsonx (see
`improments.md` for the follow-up list this version implements).

This is a **self-contained project**. It has its own venv, dependencies, config and tests,
and it shares nothing with the surrounding `langchain-playground` at runtime.

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
interpreter, run `make venv PYTHON_BIN=/path/to/python3.14`. After pulling dependency
changes, run `make install` again.

## Run

```bash
make run        # dev server with debugger + auto-reload -> http://127.0.0.1:5000
make serve      # gunicorn, production-style             -> http://127.0.0.1:5000
```

`HOST` and `PORT` can be overridden: `make run PORT=8000`.

Try it from the terminal without the browser. It makes one billed call per model and
skips the cache and memory:

```bash
.venv/bin/flask --app genai_app ask "I was charged twice for my order" -m claude-haiku-5-5
.venv/bin/flask --app genai_app ask "I was charged twice for my order"   # every model
```

> **Cost:** an A/B test makes one billed call per selected model. Opus and Fable cost the
> most, so untick them in the A/B picker when you don't need them.

## Configuration

Everything comes from environment variables, which are also read from this folder's
`.env`. `.env.sample` lists them all.

| Variable                | Default                    | Notes                                                       |
| ----------------------- | -------------------------- | ----------------------------------------------------------- |
| `ANTHROPIC_API_KEY`     | (required)                 | The app refuses to start without it.                        |
| `ANTHROPIC_MODELS`      | all four models            | Comma-separated ids offered in the UI and API.              |
| `ANTHROPIC_MODEL`       | `claude-sonnet-5-5`        | Default model; must be one of `ANTHROPIC_MODELS`.           |
| `ANTHROPIC_MAX_TOKENS`  | `2048`                     | Claude's adaptive thinking counts against this limit too.   |
| `ANTHROPIC_TIMEOUT`     | `120`                      | Seconds per API request.                                    |
| `ANTHROPIC_MAX_RETRIES` | `2`                        | SDK retries with backoff on connection errors, 429 and 5xx. |
| `MEMORY_MAX_TURNS`      | `10`                       | Earlier turns sent with each message.                       |
| `CACHE_TYPE`            | `SimpleCache`              | `SimpleCache` (per process), `RedisCache`, or `NullCache` (off). |
| `CACHE_DEFAULT_TIMEOUT` | `3600`                     | Seconds a cached answer stays valid.                        |
| `CACHE_REDIS_URL`       |                            | Needed with `RedisCache` (also `pip install redis`).        |
| `DATABASE`              | `instance/genai_app.sqlite3` | SQLite file for memory and A/B results (gitignored).      |
| `LOG_LEVEL`             | `INFO`                     | `DEBUG` also logs static file requests.                     |

## How the features work

### Streaming

Both `/api/generate` and `/api/compare` take `"stream": true`. They then answer with
Server-Sent Events (`text/event-stream`) instead of one JSON body. This is the same framing
the OpenAI and Anthropic APIs use for streaming.

The answer is a JSON object, so the server doesn't just relay raw tokens. With every token
it also sends `partial`, the analysis parsed from the text received so far (LangChain's
`parse_json_markdown`, which tolerates unfinished JSON). The page re-renders the card from
`partial`, so the summary grows word by word and the category and sentiment appear as soon
as they are written. Thinking tokens are not streamed. Until the first answer token
arrives, the card shows "Thinking...".

How the layers split the work:

| Layer | Streaming part |
| --- | --- |
| `services/assistant.py` | `stream()` yields an `AnalysisDelta` per text chunk, then the final `ModelReply`. `analyze()` (blocking) shares the same `_finish()`: stop reason check, parsing, validation |
| `services/triage.py` | `stream()` runs one thread per model and merges their deltas through a queue into one ordered sequence of events: `ModelDelta*`, `ModelFinished` per model (cache hits finish at once), then `RunCompleted`. `run()` (blocking) shares the plan, cache and memory steps |
| `api/streaming.py` | turns those service events into SSE events |
| `api/sse.py` | SSE framing and the streaming `Response` |
| `static/js/api.js` | `streamEvents()` reads the stream with `fetch` (`EventSource` can't POST) |

Streaming and complete answers go through the same cache, memory and A/B storage. A
streamed answer is cached and remembered just like a complete one.

If the browser disconnects mid-stream (tab closed, **Clear Chat**), the server stops reading
the model streams, so no more tokens are generated, and nothing is recorded. A failed model
doesn't break the stream: it arrives as a `result` event with `ok: false`. Only an
unexpected server error ends the stream early, with a final `error` event.

### Models

`services/catalog.py` maps model ids to display names. `build_chat_models()` creates one
`ChatAnthropic` per id in `ANTHROPIC_MODELS` at startup. All of them share one prompt and
one output schema, so they are directly comparable.

### A/B testing

`POST /api/compare` sends the message to every selected model at once, on a thread pool,
so an A/B test takes about as long as its slowest model, not the sum of all of them. A
model that fails doesn't sink the comparison: its card shows the error, and the other
models' answers still show. The run is saved (`comparisons` and `comparison_results`
tables), and each vote sets that run's winner. A second vote changes it.

`GET /api/comparisons/stats` aggregates per model:

- **runs** and **errors**
- **wins** and **win rate**, counted over the voted runs the model took part in
- **average latency** and **average output tokens**, counted over real calls only, since
  cache hits would make a model look fast

### Conversation memory

The prompt has a LangChain `MessagesPlaceholder("history")` between the system prompt and
the new message. The browser keeps a `conversation_id`, which the server issues on the
first message. Each turn (the user message plus each model's JSON answer) is stored in
SQLite, and the last `MEMORY_MAX_TURNS` turns are replayed as `HumanMessage`/`AIMessage`
pairs.

In an A/B turn every model answered, so each model is shown **its own** earlier answer and
the threads don't get mixed. A model that didn't take part in a turn is shown the answer
that was recorded first. That's why switching models mid-conversation keeps the context.
Failed turns are not stored.

### Caching

Answers are cached with Flask-Caching. The key is a hash of the model, the history, the
message and a fingerprint of the prompt and schema. So:

- the same question asked in a fresh conversation, or after Clear Chat, is a cache hit
- the same words in a different context are not, because the context changes the answer
- editing the prompt or schema invalidates old entries automatically

Hits show a green **cached** badge, and only successful answers are cached. `SimpleCache`
lives in each gunicorn worker. Use `RedisCache` to share the cache between workers.

### Error handling and logging

Errors use typed exceptions (`exceptions.py`), and the API turns each one into
`{"error": {"code", "message"}, "request_id"}`:

| Status | `code`                                          | When                                                     |
| ------ | ----------------------------------------------- | -------------------------------------------------------- |
| 400    | `invalid_request`                               | bad JSON, empty/too long message, unknown model, < 2 models to compare |
| 404    | `not_found`                                     | unknown route or comparison                              |
| 413    | `request_entity_too_large`                      | body over 16 KB                                          |
| 429    | `upstream_rate_limited`                         | Anthropic rate limit, after the SDK's retries            |
| 502    | `model_output_invalid` / `model_output_truncated` / `model_refused` | the reply was malformed, cut off at `ANTHROPIC_MAX_TOKENS`, or refused |
| 502    | `upstream_auth` / `model_not_available` / `upstream_error` | bad API key, model not enabled for the key, other API errors |
| 503    | `upstream_unavailable`                          | API unreachable or overloaded                            |
| 504    | `upstream_timeout`                              | API took longer than `ANTHROPIC_TIMEOUT`                 |
| 500    | `internal_error`                                | anything unexpected; details only in the log            |

A truncated reply is detected from the response's `stop_reason` before parsing, so it is
reported as such instead of as a vague JSON error.

Every request gets an id. An incoming `X-Request-ID` header is reused, and the id is sent
back in the response header. It is stamped on every log line, including lines from the
threads that call the models:

```
2026-10-12 15:51:51,332 WARNING [d0ed28a5...] genai_app.services.triage: model=claude-haiku-5-5 failed in 0.69s: model_output_invalid
2026-10-12 15:51:51,333 INFO    [d0ed28a5...] genai_app.access: POST /api/compare -> 200 in 689ms
```

Error messages in the UI show the first 8 characters of the request id, so you can find
the matching log lines.

## API

| Method | Path                                    | Body                                          | Returns |
| ------ | --------------------------------------- | --------------------------------------------- | ------- |
| GET    | `/api/health`                           |                                               | `{status, models}` |
| GET    | `/api/models`                           |                                               | `{default, models: [{id, label}]}` |
| POST   | `/api/generate`                         | `{message, model?, conversation_id?}`         | `{conversation_id, result}` |
| POST   | `/api/compare`                          | `{message, models: [≥2 ids], conversation_id?}` | `{comparison_id, conversation_id, results: [...]}` |
| POST   | `/api/comparisons/<id>/vote`            | `{model}`                                     | `{comparison_id, winner}` |
| GET    | `/api/comparisons/stats`                |                                               | `{models: [{model, label, runs, errors, votes, wins, win_rate, avg_duration, avg_output_tokens}]}` |
| DELETE | `/api/conversations/<id>`               |                                               | 204, memory forgotten |

`/api/generate` and `/api/compare` also accept `"stream": true`. The response is then
`text/event-stream`, with these events in order:

| Event | Data | When |
| --- | --- | --- |
| `start` | `{conversation_id, models: [{id, label}]}` | first |
| `delta` | `{model, text, partial}` | for every text chunk, per model; `partial` is the analysis so far, with some fields possibly missing |
| `result` | the same `result` object as below | when a model finishes, ok or failed (cache hits: right away, with no deltas) |
| `done` | `{conversation_id, comparison_id}` | last; `comparison_id` only for A/B runs with at least one answer |
| `error` | `{error: {code, message}, request_id}` | only if the server fails unexpectedly mid-stream |

Validation errors still come back as normal JSON 4xx responses, before any stream starts.

```bash
curl -N localhost:5000/api/generate -H 'Content-Type: application/json' \
  -d '{"message": "My internet has been down since yesterday!", "stream": true}'
```

Each `result` looks like this:

```json
{
  "model": "claude-sonnet-5-5",
  "label": "Claude Sonnet 5.5",
  "ok": true,
  "analysis": {"summary": "...", "sentiment": 15, "category": "technical", "action": "..."},
  "error": null,
  "duration": 2.413,
  "cached": false,
  "usage": {"input_tokens": 512, "output_tokens": 96}
}
```

A failed model in a comparison has `ok: false`, `analysis: null` and an `error` with
`code` and `message`. Example:

```bash
curl -s localhost:5000/api/compare -H 'Content-Type: application/json' \
  -d '{"message": "My internet has been down since yesterday!", "models": ["claude-sonnet-5-5", "claude-haiku-5-5"]}'
```

## Project layout

```
04_genai_flask_app/
├── pyproject.toml             # package metadata, pinned deps, pytest + ruff config
├── Makefile                   # setup / run / serve / test / lint
├── .env.sample                # every setting, documented; copy to .env (gitignored)
├── improments.md              # the follow-up list this version implements
├── src/genai_app/
│   ├── __init__.py            # create_app(): the application factory
│   ├── config.py              # Config / TestingConfig, read from the environment + .env
│   ├── extensions.py          # Flask-Caching instance
│   ├── db.py                  # per-request SQLite connection, schema setup
│   ├── schema.sql             # memory + A/B tables
│   ├── exceptions.py          # AppError hierarchy: status + code + safe message
│   ├── errors.py              # error handlers: JSON for /api, HTML elsewhere
│   ├── logs.py                # logging config, request ids, access log
│   ├── cli.py                 # `flask ask "<message>" [-m model ...]`
│   ├── services/
│   │   ├── catalog.py         # model ids -> display names
│   │   ├── assistant.py       # LangChain: prompt | ChatAnthropic, parsing, API error mapping
│   │   ├── triage.py          # one or many models: cache, memory, parallel calls, blocking or streamed
│   │   ├── memory.py          # conversation history in SQLite -> chat messages
│   │   └── comparisons.py     # A/B runs, votes, stats
│   ├── api/                   # blueprint mounted at /api
│   │   ├── routes.py          # thin: validate, call a service, serialize (JSON or stream)
│   │   ├── schemas.py         # pydantic request/response/stream-event models
│   │   ├── streaming.py       # service events -> SSE events
│   │   └── sse.py             # SSE framing + streaming Response
│   ├── web/                   # blueprint for the HTML page
│   │   └── routes.py
│   ├── templates/             # base.html, index.html (Jinja)
│   └── static/
│       ├── css/styles.css
│       └── js/                # ES modules, no build step
│           ├── app.js         # entry point: sends messages, JSON or streaming
│           ├── api.js         # fetch helpers + Server-Sent Events reader
│           ├── components.js  # messages, result cards, single answer / comparison views
│           ├── controls.js    # A/B + Stream switches, model pickers (remembered)
│           ├── stats.js       # A/B results dialog
│           └── dom.js         # el() helper
└── tests/                     # pytest; models are faked, no API calls
```

How the pieces fit together:

- **Application factory.** `create_app(config=None, *, chat_models=None)` builds the app.
  Tests pass `TestingConfig` (with a temporary SQLite file) and fake chat models.
- **Thin routes.** A route validates its input with pydantic, calls a service, and
  serializes the result. Services never touch `request`.
- **One view interface on the page.** The single-answer view and the A/B view both expose
  `update / finish / fail / complete`. `app.js` feeds them from a JSON response or from a
  stream without caring which view it has.
- **Model output is never parsed as HTML.** It reaches the page only through
  `textContent`.

## Tests and lint

```bash
make test         # pytest: 70 tests with scripted fake models, free and offline
make lint         # ruff check --fix + ruff format
make lint-check   # checks only, no writes
```
