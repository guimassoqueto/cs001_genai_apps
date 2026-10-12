import contextvars
import hashlib
import json
import logging
import threading
import time
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import dataclass, field
from queue import Queue
from typing import Any

from flask_caching import Cache
from langchain_core.messages import BaseMessage

from genai_app.exceptions import AppError, StreamCancelled
from genai_app.services.assistant import InquiryAnalysis, InquiryAssistant, ModelReply
from genai_app.services.memory import ConversationMemory

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ModelResult:
    """What one model produced for one message: a reply, or the error that replaced it."""

    model: str
    duration: float
    cached: bool = False
    reply: ModelReply | None = None
    error: AppError | None = None

    @property
    def ok(self) -> bool:
        return self.reply is not None


# --- Streaming events, in the order a client receives them --------------------------------


@dataclass(frozen=True, slots=True)
class ModelDelta:
    """A model wrote more of its answer. `partial` is the analysis parsed so far."""

    model: str
    text: str
    partial: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ModelFinished:
    """A model is done: its final result, or its error."""

    result: ModelResult


@dataclass(frozen=True, slots=True)
class RunCompleted:
    """Every model is done and the turn is recorded. `results` follows the requested model order."""

    results: list[ModelResult]


TriageEvent = ModelDelta | ModelFinished | RunCompleted


@dataclass(slots=True)
class _Plan:
    """Everything known before any model is called."""

    model_ids: list[str]
    histories: dict[str, list[BaseMessage]]
    cache_keys: dict[str, str]
    cached: dict[str, ModelResult] = field(default_factory=dict)

    @property
    def pending(self) -> list[str]:
        return [model_id for model_id in self.model_ids if model_id not in self.cached]


class TriageService:
    """Sends a message to one or more models, with response caching and conversation memory.

    Two modes share every step except how the answers are delivered:
      run()    - blocking: returns once every model has answered.
      stream() - yields the answers token by token while the models write them.

    Several models always run in parallel, one thread each. Built per request: it holds the
    request's database connection.
    """

    def __init__(self, assistant: InquiryAssistant, memory: ConversationMemory, cache: Cache) -> None:
        self.assistant = assistant
        self.memory = memory
        self.cache = cache

    def run(self, message: str, model_ids: list[str], conversation_id: str) -> list[ModelResult]:
        """Analyze `message` with every model and record the turn.

        Never raises for a model failure: each result carries its own error.
        """
        plan = self._plan(message, model_ids, conversation_id)
        results = dict(plan.cached)

        if plan.pending:
            with ThreadPoolExecutor(max_workers=len(plan.pending), thread_name_prefix="model") as pool:
                futures = {}
                for model_id in plan.pending:
                    analyze = _in_request_context(self._analyze)
                    futures[model_id] = pool.submit(analyze, model_id, message, plan.histories[model_id])
            results |= {model_id: future.result() for model_id, future in futures.items()}

        return self._record(plan, message, conversation_id, results)

    def stream(self, message: str, model_ids: list[str], conversation_id: str) -> Iterator[TriageEvent]:
        """Like run(), but yields events as they happen: ModelDelta while a model writes,
        ModelFinished when it is done (cache hits finish at once), then one RunCompleted.

        If the consumer stops early (the client disconnected), the model streams are abandoned
        and nothing is recorded.
        """
        plan = self._plan(message, model_ids, conversation_id)
        results = dict(plan.cached)
        for result in plan.cached.values():
            yield ModelFinished(result)

        if plan.pending:
            events: Queue[ModelDelta | ModelFinished] = Queue()
            stop = threading.Event()
            with ThreadPoolExecutor(max_workers=len(plan.pending), thread_name_prefix="model") as pool:
                for model_id in plan.pending:
                    stream_one = _in_request_context(self._stream_one)
                    pool.submit(stream_one, model_id, message, plan.histories[model_id], events, stop)
                try:
                    while len(results) < len(model_ids):
                        event = events.get()
                        if isinstance(event, ModelFinished):
                            results[event.result.model] = event.result
                        yield event
                finally:
                    stop.set()  # normal end: no-op; client gone: the model threads stop reading

        yield RunCompleted(self._record(plan, message, conversation_id, results))

    # --- Steps shared by both modes ----------------------------------------------------------

    def _plan(self, message: str, model_ids: list[str], conversation_id: str) -> _Plan:
        histories = {model_id: self.memory.history(conversation_id, model_id) for model_id in model_ids}
        plan = _Plan(
            model_ids=model_ids,
            histories=histories,
            cache_keys={model_id: self._cache_key(model_id, histories[model_id], message) for model_id in model_ids},
        )
        for model_id in model_ids:
            hit = self.cache.get(plan.cache_keys[model_id])
            if hit is not None:
                logger.info("model=%s cache hit", model_id)
                reply = ModelReply(analysis=InquiryAnalysis.model_validate(hit), usage=None)
                plan.cached[model_id] = ModelResult(model=model_id, duration=0.0, cached=True, reply=reply)
        return plan

    def _record(
        self, plan: _Plan, message: str, conversation_id: str, results: dict[str, ModelResult]
    ) -> list[ModelResult]:
        """Cache the new answers and store the turn in memory. Returns results in request order."""
        ordered = [results[model_id] for model_id in plan.model_ids]
        for result in ordered:
            if result.ok and not result.cached:
                self.cache.set(plan.cache_keys[result.model], result.reply.analysis.model_dump())

        replies = {r.model: r.reply.analysis.model_dump_json() for r in ordered if r.ok}
        if replies:
            self.memory.record(conversation_id, message, replies)
        return ordered

    # --- One model, one thread ------------------------------------------------------------------

    def _analyze(self, model_id: str, message: str, history: list[BaseMessage]) -> ModelResult:
        return _guarded(model_id, lambda: self.assistant.analyze(model_id, message, history))

    def _stream_one(
        self,
        model_id: str,
        message: str,
        history: list[BaseMessage],
        events: Queue[ModelDelta | ModelFinished],
        stop: threading.Event,
    ) -> None:
        def consume() -> ModelReply:
            with closing(self.assistant.stream(model_id, message, history)) as updates:
                for update in updates:
                    if stop.is_set():
                        raise StreamCancelled()
                    if isinstance(update, ModelReply):
                        return update
                    events.put(ModelDelta(model=model_id, text=update.text, partial=update.partial))
            raise AssertionError("assistant.stream() ended without a reply")

        events.put(ModelFinished(_guarded(model_id, consume)))

    def _cache_key(self, model_id: str, history: list[BaseMessage], message: str) -> str:
        # The context changes the answer, so the history is part of the key, not just the message.
        payload = json.dumps(
            {
                "prompt": self.assistant.prompt_fingerprint,
                "model": model_id,
                "history": [[m.type, m.text] for m in history],
                "message": message,
            },
            sort_keys=True,
        )
        return "analysis:" + hashlib.sha256(payload.encode()).hexdigest()


def _guarded(model_id: str, call: Callable[[], ModelReply]) -> ModelResult:
    """Run one model call, timing it and turning any failure into an error result."""
    start = time.perf_counter()
    try:
        reply = call()
    except AppError as error:
        result = ModelResult(model=model_id, duration=time.perf_counter() - start, error=error)
        logger.warning("model=%s failed in %.2fs: %s", model_id, result.duration, error.code)
        return result
    except Exception:
        logger.exception("model=%s unexpected error", model_id)
        return ModelResult(model=model_id, duration=time.perf_counter() - start, error=AppError())

    result = ModelResult(model=model_id, duration=time.perf_counter() - start, reply=reply)
    usage = reply.usage
    logger.info(
        "model=%s ok in %.2fs tokens_in=%s tokens_out=%s",
        model_id,
        result.duration,
        usage.input_tokens if usage else "?",
        usage.output_tokens if usage else "?",
    )
    return result


def _in_request_context[**P, R](func: Callable[P, R]) -> Callable[P, R]:
    """Wrap `func` to run in a copy of the caller's context, so worker threads log the request id."""
    context = contextvars.copy_context()
    return lambda *args, **kwargs: context.run(func, *args, **kwargs)
