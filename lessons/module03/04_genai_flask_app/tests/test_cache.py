from genai_app import create_app
from tests.conftest import HAIKU, analysis_json


def test_repeated_query_is_served_from_the_cache(client, sonnet):
    sonnet.replies.append(analysis_json())

    first = client.post("/api/generate", json={"message": "I was charged twice!"}).get_json()
    second = client.post("/api/generate", json={"message": "I was charged twice!"}).get_json()

    assert len(sonnet.calls) == 1
    assert first["result"]["cached"] is False
    assert second["result"]["cached"] is True
    assert second["result"]["analysis"] == first["result"]["analysis"]
    assert second["result"]["duration"] == 0


def test_cache_is_per_model(client, sonnet, haiku):
    sonnet.replies.append(analysis_json())
    haiku.replies.append(analysis_json(summary="haiku"))

    client.post("/api/generate", json={"message": "same text"})
    response = client.post("/api/generate", json={"message": "same text", "model": HAIKU}).get_json()

    assert response["result"]["cached"] is False
    assert response["result"]["analysis"]["summary"] == "haiku"


def test_same_message_with_different_context_is_not_a_hit(client, sonnet):
    sonnet.replies += [analysis_json(), analysis_json(summary="in context")]

    conversation = client.post("/api/generate", json={"message": "same text"}).get_json()["conversation_id"]
    response = client.post("/api/generate", json={"message": "same text", "conversation_id": conversation}).get_json()

    assert response["result"]["cached"] is False
    assert len(sonnet.calls) == 2


def test_failures_are_not_cached(client, sonnet):
    sonnet.replies += ["not json", analysis_json()]

    assert client.post("/api/generate", json={"message": "hello"}).status_code == 502
    response = client.post("/api/generate", json={"message": "hello"}).get_json()

    assert response["result"]["cached"] is False
    assert len(sonnet.calls) == 2


def test_null_cache_disables_caching(config, chat_models):
    config.CACHE_TYPE = "NullCache"
    client = create_app(config, chat_models=chat_models).test_client()
    sonnet = chat_models["claude-sonnet-5-5"]
    sonnet.replies += [analysis_json(), analysis_json()]

    client.post("/api/generate", json={"message": "hello"})
    response = client.post("/api/generate", json={"message": "hello"}).get_json()

    assert response["result"]["cached"] is False
    assert len(sonnet.calls) == 2
