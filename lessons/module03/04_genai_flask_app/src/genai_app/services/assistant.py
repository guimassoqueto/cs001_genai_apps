import hashlib
import logging
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

import anthropic
from flask import Flask
from langchain_anthropic import ChatAnthropic
from langchain_core.exceptions import OutputParserException
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.utils.json import parse_json_markdown
from pydantic import BaseModel, Field

from genai_app import exceptions as exc

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are an AI assistant helping with customer inquiries. Provide a helpful and concise response. "
    "Earlier messages in the conversation are context: analyze the latest customer message in light of them."
)


class InquiryAnalysis(BaseModel):
    """Structured triage of one customer message, as returned by the model."""

    summary: str = Field(description="Summary of the user's message")
    sentiment: int = Field(ge=0, le=100, description="Sentiment score from 0 (negative) to 100 (positive)")
    category: str = Field(description="Category of the inquiry (e.g., billing, technical, general)")
    action: str = Field(description="Recommended action for the support rep")


class Usage(BaseModel):
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True, slots=True)
class ModelReply:
    """A model's finished, validated answer."""

    analysis: InquiryAnalysis
    usage: Usage | None


@dataclass(frozen=True, slots=True)
class AnalysisDelta:
    """One streamed piece of reply text, plus the analysis parsed from all the text received so far."""

    text: str
    partial: dict[str, Any]


class InquiryAssistant:
    """Runs a customer message, plus the conversation so far, through one of the configured models."""

    def __init__(self, chat_models: Mapping[str, BaseChatModel]) -> None:
        self.parser = PydanticOutputParser(pydantic_object=InquiryAnalysis)
        format_instructions = self.parser.get_format_instructions()
        # Fixed values go in through .partial(): the format instructions contain JSON braces
        # that must not be parsed as template variables.
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "{system_prompt}\n\n{format_instructions}"),
                MessagesPlaceholder("history", optional=True),  # conversation memory
                ("human", "{message}"),
            ]
        ).partial(system_prompt=SYSTEM_PROMPT, format_instructions=format_instructions)
        # prompt | model only: the parser runs separately, so the raw AIMessage (stop reason,
        # token usage) can be inspected first.
        self._chains = {model_id: prompt | model for model_id, model in chat_models.items()}
        # Changes whenever the prompt or the output schema changes, so stale cache entries stop matching.
        self.prompt_fingerprint = hashlib.sha256(f"{SYSTEM_PROMPT}\n{format_instructions}".encode()).hexdigest()

    @property
    def model_ids(self) -> list[str]:
        return list(self._chains)

    def analyze(self, model_id: str, message: str, history: list[BaseMessage] | None = None) -> ModelReply:
        """Ask one model for an analysis and wait for the whole answer.

        Raises:
            AppError: a subclass describing what went wrong (API error, truncated or invalid reply).
        """
        with _translated_api_errors():
            reply = self._chains[model_id].invoke(_inputs(message, history))
        return self._finish(model_id, reply)

    def stream(
        self, model_id: str, message: str, history: list[BaseMessage] | None = None
    ) -> Iterator[AnalysisDelta | ModelReply]:
        """Ask one model for an analysis, token by token.

        Yields an AnalysisDelta for every piece of reply text as it arrives, then the final
        ModelReply. Raises AppError like analyze(), possibly after some deltas.
        """
        reply = None
        text = ""
        with _translated_api_errors():
            for chunk in self._chains[model_id].stream(_inputs(message, history)):
                reply = chunk if reply is None else reply + chunk
                # Thinking blocks carry no text: only the visible answer is streamed.
                if chunk.text:
                    text += chunk.text
                    yield AnalysisDelta(text=chunk.text, partial=_parse_partial(text))
        if reply is None:
            raise exc.ModelOutputInvalid("The model returned an empty reply.")
        yield self._finish(model_id, reply)

    def _finish(self, model_id: str, reply: AIMessage) -> ModelReply:
        """Check how the reply ended, then parse and validate it."""
        stop_reason = reply.response_metadata.get("stop_reason")
        if stop_reason == "max_tokens":
            raise exc.ModelOutputTruncated()
        if stop_reason == "refusal":
            raise exc.ModelRefused()

        try:
            analysis = self.parser.invoke(reply)
        except OutputParserException as error:
            logger.warning("model=%s reply did not match the schema: %s", model_id, error)
            raise exc.ModelOutputInvalid() from error

        usage = reply.usage_metadata
        return ModelReply(
            analysis=analysis,
            usage=Usage(input_tokens=usage["input_tokens"], output_tokens=usage["output_tokens"]) if usage else None,
        )


def _inputs(message: str, history: list[BaseMessage] | None) -> dict[str, Any]:
    return {"message": message, "history": history or []}


def _parse_partial(text: str) -> dict[str, Any]:
    """Best-effort parse of an unfinished JSON reply: '{"summary": "Cust' -> {"summary": "Cust"}."""
    try:
        parsed = parse_json_markdown(text)
    except ValueError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


@contextmanager
def _translated_api_errors() -> Iterator[None]:
    try:
        yield
    except anthropic.APIError as error:
        raise translate_api_error(error) from error


def translate_api_error(error: anthropic.APIError) -> exc.AppError:
    """Map an Anthropic SDK error (raised after the SDK's own retries) to an application error."""
    match error:
        case anthropic.AuthenticationError() | anthropic.PermissionDeniedError():
            translated = exc.UpstreamAuthError()
        case anthropic.NotFoundError():
            translated = exc.ModelNotAvailable()
        case anthropic.RateLimitError():
            translated = exc.UpstreamRateLimited()
        case anthropic.APITimeoutError():  # before APIConnectionError, its parent class
            translated = exc.UpstreamTimeout()
        case anthropic.APIConnectionError():
            translated = exc.UpstreamUnavailable("Could not reach the Anthropic API. Try again shortly.")
        case anthropic.APIStatusError(status_code=status) if status >= 500:
            translated = exc.UpstreamUnavailable()
        case _:
            translated = exc.UpstreamError()
    logger.error("Anthropic API error (%s): %s", type(error).__name__, error)
    return translated


def build_chat_models(app: Flask) -> dict[str, BaseChatModel]:
    return {
        model_id: ChatAnthropic(
            model=model_id,
            max_tokens=app.config["ANTHROPIC_MAX_TOKENS"],
            api_key=app.config["ANTHROPIC_API_KEY"],
            timeout=app.config["ANTHROPIC_TIMEOUT"],
            max_retries=app.config["ANTHROPIC_MAX_RETRIES"],
        )
        for model_id in app.config["ANTHROPIC_MODELS"]
    }


def get_assistant(app: Flask) -> InquiryAssistant:
    return app.extensions["assistant"]
