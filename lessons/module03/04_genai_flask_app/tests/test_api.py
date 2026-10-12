import pytest


def test_health(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "model": "claude-sonnet-5-5"}


def test_generate_returns_structured_analysis(client, replies, valid_reply, valid_analysis):
    replies.append(valid_reply)

    response = client.post("/api/generate", json={"message": "I was charged twice!"})

    assert response.status_code == 200
    body = response.get_json()
    assert body["analysis"] == valid_analysis
    assert body["model"] == "claude-sonnet-5-5"
    assert body["duration"] >= 0


def test_generate_accepts_json_wrapped_in_a_code_fence(client, replies, valid_reply, valid_analysis):
    replies.append(f"```json\n{valid_reply}\n```")

    response = client.post("/api/generate", json={"message": "I was charged twice!"})

    assert response.status_code == 200
    assert response.get_json()["analysis"] == valid_analysis


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"message": ""},
        {"message": "   "},
        {"message": "x" * 4001},
        {"message": "hi", "model": "llama"},
    ],
)
def test_generate_rejects_invalid_payloads(client, payload):
    response = client.post("/api/generate", json=payload)

    assert response.status_code == 400
    assert "error" in response.get_json()


def test_generate_rejects_non_json_body(client):
    response = client.post("/api/generate", data="hello", content_type="text/plain")

    assert response.status_code == 400
    assert response.get_json() == {"error": "Request body must be a JSON object."}


@pytest.mark.parametrize(
    "reply",
    [
        "Sorry, I can't help with that.",
        '{"summary": "cut off mid-',
        '{"summary": "s", "sentiment": 150, "category": "c", "action": "a"}',
    ],
)
def test_generate_reports_unparseable_model_output(client, replies, reply):
    replies.append(reply)

    response = client.post("/api/generate", json={"message": "hello"})

    assert response.status_code == 502
    assert "ANTHROPIC_MAX_TOKENS" in response.get_json()["error"]


def test_unknown_api_route_returns_json(client):
    response = client.get("/api/nope")

    assert response.status_code == 404
    assert "error" in response.get_json()


def test_wrong_method_returns_json(client):
    response = client.get("/api/generate")

    assert response.status_code == 405
    assert "error" in response.get_json()
