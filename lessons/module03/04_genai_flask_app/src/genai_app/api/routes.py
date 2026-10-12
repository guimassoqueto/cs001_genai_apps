import uuid
from uuid import UUID

from flask import current_app, jsonify, request
from pydantic import BaseModel, ValidationError

from genai_app.api import bp
from genai_app.api.schemas import (
    CompareRequest,
    CompareResponse,
    GenerateRequest,
    GenerateResponse,
    ModelResultOut,
    VoteRequest,
)
from genai_app.api.sse import sse_response
from genai_app.api.streaming import triage_events
from genai_app.db import get_db
from genai_app.exceptions import InvalidRequest
from genai_app.extensions import cache
from genai_app.services.assistant import get_assistant
from genai_app.services.catalog import model_info
from genai_app.services.comparisons import ComparisonStore
from genai_app.services.memory import ConversationMemory
from genai_app.services.triage import ModelResult, TriageService


def _parse[T: BaseModel](schema: type[T]) -> T:
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise InvalidRequest("Request body must be a JSON object.")
    try:
        return schema.model_validate(body)
    except ValidationError as error:
        details = "; ".join(f"{'.'.join(map(str, e['loc'])) or 'body'}: {e['msg']}" for e in error.errors())
        raise InvalidRequest(details) from error


def _check_models(model_ids: list[str]) -> None:
    available = current_app.config["ANTHROPIC_MODELS"]
    unknown = [model_id for model_id in model_ids if model_id not in available]
    if unknown:
        raise InvalidRequest(f"Unknown model: {', '.join(unknown)}. Available: {', '.join(available)}.")


def _memory() -> ConversationMemory:
    return ConversationMemory(get_db(), current_app.config["MEMORY_MAX_TURNS"])


def _triage() -> TriageService:
    return TriageService(get_assistant(current_app), _memory(), cache)


def _conversation_id(requested: UUID | None) -> str:
    return str(requested or uuid.uuid4())


@bp.get("/health")
def health():
    return jsonify(status="ok", models=current_app.config["ANTHROPIC_MODELS"])


@bp.get("/models")
def models():
    return jsonify(
        default=current_app.config["ANTHROPIC_MODEL"],
        models=[{"id": m, "label": model_info(m).label} for m in current_app.config["ANTHROPIC_MODELS"]],
    )


@bp.post("/generate")
def generate():
    """Analyze a message with one model. With "stream": true the answer arrives as Server-Sent Events."""
    payload = _parse(GenerateRequest)
    model_id = payload.model or current_app.config["ANTHROPIC_MODEL"]
    _check_models([model_id])
    conversation_id = _conversation_id(payload.conversation_id)

    if payload.stream:
        return sse_response(triage_events(_triage, payload.message, [model_id], conversation_id))

    [result] = _triage().run(payload.message, [model_id], conversation_id)
    if result.error:
        raise result.error

    response = GenerateResponse(conversation_id=conversation_id, result=ModelResultOut.from_result(result))
    return jsonify(response.model_dump())


@bp.post("/compare")
def compare():
    """A/B test: analyze the same message with several models in parallel. Streams like /generate."""
    payload = _parse(CompareRequest)
    _check_models(payload.models)
    conversation_id = _conversation_id(payload.conversation_id)

    if payload.stream:
        return sse_response(
            triage_events(
                _triage,
                payload.message,
                payload.models,
                conversation_id,
                on_completed=lambda results: _save_comparison(conversation_id, results),
            )
        )

    results = _triage().run(payload.message, payload.models, conversation_id)
    if not any(r.ok for r in results):
        raise results[0].error

    response = CompareResponse(
        comparison_id=_save_comparison(conversation_id, results),
        conversation_id=conversation_id,
        results=[ModelResultOut.from_result(r) for r in results],
    )
    return jsonify(response.model_dump())


def _save_comparison(conversation_id: str, results: list[ModelResult]) -> str | None:
    """Store an A/B run so it can be voted on; a run where every model failed is not stored."""
    if not any(r.ok for r in results):
        return None
    return ComparisonStore(get_db()).create(conversation_id, results)


@bp.post("/comparisons/<uuid:comparison_id>/vote")
def vote(comparison_id: UUID):
    """Record which model's answer the user preferred (calling it again changes the vote)."""
    payload = _parse(VoteRequest)
    ComparisonStore(get_db()).vote(str(comparison_id), payload.model)
    return jsonify(comparison_id=str(comparison_id), winner=payload.model)


@bp.get("/comparisons/stats")
def comparison_stats():
    stats = ComparisonStore(get_db()).stats()
    for row in stats:
        row["label"] = model_info(row["model"]).label
    return jsonify(models=stats)


@bp.delete("/conversations/<uuid:conversation_id>")
def clear_conversation(conversation_id: UUID):
    """Forget a conversation's memory."""
    _memory().clear(str(conversation_id))
    return "", 204
