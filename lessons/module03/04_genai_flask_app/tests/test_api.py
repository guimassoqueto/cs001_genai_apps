import json
import uuid

import anthropic
import httpx
import pytest
from langchain_core.messages import AIMessage

from tests.conftest import HAIKU, SONNET, analysis_json


def _status_error(cls, status: int):
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls("boom", response=httpx.Response(status, request=request), body=None)


def _request():
    return httpx.Request("POST", "https://api.anthropic.com/v1/messages")


def test_health(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_models_lists_the_catalog_with_labels(client):
    body = client.get("/api/models").get_json()

    assert body["default"] == SONNET
    assert {"id": "claude-fable-5-1", "label": "Claude Fable 5.1"} in body["models"]
    assert len(body["models"]) == 4


def test_generate_uses_the_default_model(client, sonnet):
    sonnet.replies.append(
        AIMessage(analysis_json(), usage_metadata={"input_tokens": 120, "output_tokens": 40, "total_tokens": 160})
    )

    response = client.post("/api/generate", json={"message": "I was charged twice!"})

    assert response.status_code == 200
    body = response.get_json()
    uuid.UUID(body["conversation_id"])
    result = body["result"]
    assert result["model"] == SONNET
    assert result["label"] == "Claude Sonnet 5.5"
    assert result["ok"] is True
    assert result["analysis"] == json.loads(analysis_json())
    assert result["usage"] == {"input_tokens": 120, "output_tokens": 40}
    assert result["cached"] is False


def test_generate_uses_the_selected_model(client, sonnet, haiku):
    haiku.replies.append(analysis_json())

    response = client.post("/api/generate", json={"message": "hello", "model": HAIKU})

    assert response.status_code == 200
    assert response.get_json()["result"]["model"] == HAIKU
    assert len(haiku.calls) == 1
    assert sonnet.calls == []


def test_generate_accepts_json_wrapped_in_a_code_fence(client, sonnet):
    sonnet.replies.append(f"```json\n{analysis_json()}\n```")

    response = client.post("/api/generate", json={"message": "hello"})

    assert response.status_code == 200


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"message": ""},
        {"message": "   "},
        {"message": "x" * 4001},
        {"message": "hi", "extra": 1},
        {"message": "hi", "model": "gpt-4"},
        {"message": "hi", "conversation_id": "not-a-uuid"},
    ],
)
def test_generate_rejects_invalid_payloads(client, payload):
    response = client.post("/api/generate", json=payload)

    assert response.status_code == 400
    body = response.get_json()
    assert body["error"]["code"] == "invalid_request"
    assert body["request_id"]


def test_generate_rejects_non_json_body(client):
    response = client.post("/api/generate", data="hello", content_type="text/plain")

    assert response.status_code == 400
    assert response.get_json()["error"]["message"] == "Request body must be a JSON object."


@pytest.mark.parametrize(
    ("reply", "code"),
    [
        ("Sorry, I can't help with that.", "model_output_invalid"),
        ('{"summary": "s", "sentiment": 150, "category": "c", "action": "a"}', "model_output_invalid"),
        (AIMessage('{"summary": "cut', response_metadata={"stop_reason": "max_tokens"}), "model_output_truncated"),
        (AIMessage("", response_metadata={"stop_reason": "refusal"}), "model_refused"),
    ],
)
def test_generate_reports_bad_model_output(client, sonnet, reply, code):
    sonnet.replies.append(reply)

    response = client.post("/api/generate", json={"message": "hello"})

    assert response.status_code == 502
    assert response.get_json()["error"]["code"] == code


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (_status_error(anthropic.AuthenticationError, 401), 502, "upstream_auth"),
        (_status_error(anthropic.NotFoundError, 404), 502, "model_not_available"),
        (_status_error(anthropic.BadRequestError, 400), 502, "upstream_error"),
        (_status_error(anthropic.RateLimitError, 429), 429, "upstream_rate_limited"),
        (_status_error(anthropic.InternalServerError, 500), 503, "upstream_unavailable"),
        (_status_error(anthropic.APIStatusError, 529), 503, "upstream_unavailable"),
        (anthropic.APITimeoutError(request=_request()), 504, "upstream_timeout"),
        (anthropic.APIConnectionError(request=_request()), 503, "upstream_unavailable"),
    ],
)
def test_generate_maps_anthropic_errors(client, sonnet, error, status, code):
    sonnet.replies.append(error)

    response = client.post("/api/generate", json={"message": "hello"})

    assert response.status_code == status
    assert response.get_json()["error"]["code"] == code


def test_unexpected_model_error_is_a_generic_500(client, sonnet):
    sonnet.replies.append(RuntimeError("secret internals"))

    response = client.post("/api/generate", json={"message": "hello"})

    assert response.status_code == 500
    assert response.get_json()["error"] == {"code": "internal_error", "message": "Internal server error."}


def test_every_response_carries_a_request_id(client):
    generated = client.get("/api/health")
    echoed = client.get("/api/health", headers={"X-Request-ID": "abc-123"})
    rejected = client.get("/api/health", headers={"X-Request-ID": "bad id with spaces"})

    assert len(generated.headers["X-Request-ID"]) == 32
    assert echoed.headers["X-Request-ID"] == "abc-123"
    assert rejected.headers["X-Request-ID"] != "bad id with spaces"


def test_unknown_api_route_returns_json(client):
    response = client.get("/api/nope")

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "not_found"


def test_wrong_method_returns_json(client):
    response = client.get("/api/generate")

    assert response.status_code == 405
    assert response.get_json()["error"]["code"] == "method_not_allowed"
