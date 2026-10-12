import json
from typing import Any, ClassVar

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from pydantic import Field

from genai_app import create_app
from genai_app.config import TestingConfig

SONNET = "claude-sonnet-5-5"
HAIKU = "claude-haiku-5-5"
OPUS = "claude-opus-5-5"


class ScriptedChatModel(BaseChatModel):
    """Fake chat model: returns (or raises) the queued replies in order and records every prompt.

    Supports invoke() and stream(); streaming sends the reply in CHUNK_SIZE-character chunks,
    with the response metadata (stop reason) and token usage on the last one, like ChatAnthropic.
    """

    CHUNK_SIZE: ClassVar[int] = 8

    replies: list[Any] = Field(default_factory=list)  # str | AIMessage | Exception
    calls: list[list[BaseMessage]] = Field(default_factory=list)
    chunks_sent: int = 0

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def _generate(self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=self._next_reply(messages))])

    def _stream(self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs):
        reply = self._next_reply(messages)
        text = reply.text
        pieces = [text[i : i + self.CHUNK_SIZE] for i in range(0, len(text), self.CHUNK_SIZE)] or [""]
        for i, piece in enumerate(pieces):
            last = i == len(pieces) - 1
            self.chunks_sent += 1
            yield ChatGenerationChunk(
                message=AIMessageChunk(
                    content=piece,
                    response_metadata=reply.response_metadata if last else {},
                    usage_metadata=reply.usage_metadata if last else None,
                )
            )

    def _next_reply(self, messages: list[BaseMessage]) -> AIMessage:
        self.calls.append(messages)
        if not self.replies:
            raise AssertionError("ScriptedChatModel called with no reply queued")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply if isinstance(reply, AIMessage) else AIMessage(reply)


def analysis_json(**overrides) -> str:
    analysis = {
        "summary": "Customer was charged twice for the same order.",
        "sentiment": 20,
        "category": "billing",
        "action": "Refund the duplicate charge and confirm by email.",
    }
    return json.dumps(analysis | overrides)


@pytest.fixture
def config(tmp_path):
    return TestingConfig(database=str(tmp_path / "test.sqlite3"))


@pytest.fixture
def chat_models(config):
    return {model_id: ScriptedChatModel() for model_id in config.ANTHROPIC_MODELS}


@pytest.fixture
def app(config, chat_models):
    return create_app(config, chat_models=chat_models)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def sonnet(chat_models) -> ScriptedChatModel:
    return chat_models[SONNET]


@pytest.fixture
def haiku(chat_models) -> ScriptedChatModel:
    return chat_models[HAIKU]


@pytest.fixture
def opus(chat_models) -> ScriptedChatModel:
    return chat_models[OPUS]


def read_sse(response) -> list[tuple[str, dict]]:
    """Parse a text/event-stream response body into (event, data) pairs."""
    assert response.mimetype == "text/event-stream"
    events = []
    for block in response.get_data(as_text=True).strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((fields["event"], json.loads(fields["data"])))
    return events
