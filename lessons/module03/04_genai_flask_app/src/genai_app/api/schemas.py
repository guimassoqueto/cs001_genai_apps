from typing import Annotated, Any, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from genai_app.services.assistant import InquiryAnalysis, Usage
from genai_app.services.catalog import model_info
from genai_app.services.triage import ModelResult

MAX_MESSAGE_CHARS = 4000

Message = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_MESSAGE_CHARS)]


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GenerateRequest(_Request):
    message: Message
    model: str | None = Field(default=None, description="Model id; the configured default when omitted")
    conversation_id: UUID | None = Field(default=None, description="Continue this conversation; omit to start one")
    stream: bool = Field(default=False, description="Stream the answer token by token (Server-Sent Events)")


class CompareRequest(_Request):
    message: Message
    models: list[str] = Field(min_length=2, description="Two or more distinct model ids")
    conversation_id: UUID | None = None
    stream: bool = False

    @field_validator("models")
    @classmethod
    def distinct(cls, models: list[str]) -> list[str]:
        if len(set(models)) != len(models):
            raise ValueError("models must be distinct")
        return models


class VoteRequest(_Request):
    model: str


class ErrorOut(BaseModel):
    code: str
    message: str


class ModelResultOut(BaseModel):
    model: str
    label: str
    ok: bool
    analysis: InquiryAnalysis | None
    error: ErrorOut | None
    duration: float
    cached: bool
    usage: Usage | None

    @classmethod
    def from_result(cls, result: ModelResult) -> Self:
        return cls(
            model=result.model,
            label=model_info(result.model).label,
            ok=result.ok,
            analysis=result.reply.analysis if result.reply else None,
            error=ErrorOut(**result.error.to_dict()) if result.error else None,
            duration=round(result.duration, 3),
            cached=result.cached,
            usage=result.reply.usage if result.reply else None,
        )


class GenerateResponse(BaseModel):
    conversation_id: str
    result: ModelResultOut


class CompareResponse(BaseModel):
    comparison_id: str
    conversation_id: str
    results: list[ModelResultOut]


# --- Streaming events (text/event-stream), in the order they are sent ------------------------


class ModelRef(BaseModel):
    id: str
    label: str


class StreamStart(BaseModel):
    """`start`: which models will answer, and the conversation they belong to."""

    conversation_id: str
    models: list[ModelRef]


class StreamDelta(BaseModel):
    """`delta`: a model wrote more text. `partial` is the analysis parsed so far (fields may be missing)."""

    model: str
    text: str
    partial: dict[str, Any]


# `result`: a model finished -> ModelResultOut (same shape as in the blocking responses)


class StreamDone(BaseModel):
    """`done`: every model finished. `comparison_id` is set for A/B runs with at least one answer."""

    conversation_id: str
    comparison_id: str | None = None
