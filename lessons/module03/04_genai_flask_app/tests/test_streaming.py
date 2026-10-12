import json

import anthropic
import httpx
from langchain_core.messages import AIMessage

from genai_app.services.triage import TriageService
from tests.conftest import HAIKU, SONNET, analysis_json, read_sse


def _stream_generate(client, **payload):
    return client.post("/api/generate", json={"message": "I was charged twice!", "stream": True} | payload)


def _stream_compare(client, models, **payload):
    body = {"message": "I was charged twice!", "models": models, "stream": True}
    return client.post("/api/compare", json=body | payload)


def _names(events):
    return [name for name, _ in events]


def test_generate_streams_start_deltas_result_done(client, sonnet):
    usage = {"input_tokens": 100, "output_tokens": 30, "total_tokens": 130}
    sonnet.replies.append(AIMessage(analysis_json(), usage_metadata=usage))

    response = _stream_generate(client)

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-cache"
    events = read_sse(response)
    names = _names(events)
    assert names[0] == "start"
    assert names[-2:] == ["result", "done"]
    assert set(names[1:-2]) == {"delta"}
    assert len(names[1:-2]) == sonnet.chunks_sent

    start, result, done = events[0][1], events[-2][1], events[-1][1]
    assert start["models"] == [{"id": SONNET, "label": "Claude Sonnet 5.5"}]
    assert result["ok"] is True
    assert result["analysis"] == json.loads(analysis_json())
    assert result["usage"] == {"input_tokens": 100, "output_tokens": 30}
    assert done == {"conversation_id": start["conversation_id"], "comparison_id": None}


def test_deltas_carry_the_text_and_a_growing_partial_analysis(client, sonnet):
    sonnet.replies.append(analysis_json())

    deltas = [data for name, data in read_sse(_stream_generate(client)) if name == "delta"]

    assert "".join(d["text"] for d in deltas) == analysis_json()
    summaries = [d["partial"].get("summary", "") for d in deltas]
    assert summaries == sorted(summaries, key=len)  # the summary only ever grows
    assert deltas[-1]["partial"] == json.loads(analysis_json())


def test_streamed_turns_are_remembered_and_cached(client, sonnet):
    sonnet.replies += [analysis_json(summary="first"), analysis_json()]

    start = read_sse(_stream_generate(client))[0][1]
    read_sse(_stream_generate(client, message="follow-up", conversation_id=start["conversation_id"]))
    cached = client.post("/api/generate", json={"message": "I was charged twice!"}).get_json()

    assert json.loads(sonnet.calls[1][2].content)["summary"] == "first"  # memory
    assert cached["result"]["cached"] is True  # cache, shared with the blocking mode
    assert len(sonnet.calls) == 2


def test_cache_hit_streams_the_result_without_deltas(client, sonnet):
    sonnet.replies.append(analysis_json())
    client.post("/api/generate", json={"message": "I was charged twice!"})

    events = read_sse(_stream_generate(client))

    assert _names(events) == ["start", "result", "done"]
    assert events[1][1]["cached"] is True


def test_model_failure_is_a_result_event_not_an_http_error(client, sonnet):
    sonnet.replies.append(AIMessage('{"summary": "cut', response_metadata={"stop_reason": "max_tokens"}))

    response = _stream_generate(client)

    assert response.status_code == 200
    result = read_sse(response)[-2][1]
    assert result["ok"] is False
    assert result["error"]["code"] == "model_output_truncated"


def test_api_error_is_a_result_event(client, sonnet):
    response = httpx.Response(429, request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))
    sonnet.replies.append(anthropic.RateLimitError("slow down", response=response, body=None))

    result = read_sse(_stream_generate(client))[-2][1]

    assert result["error"]["code"] == "upstream_rate_limited"


def test_invalid_request_is_still_a_json_400(client):
    response = client.post("/api/generate", json={"message": "", "stream": True})

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_request"


def test_unexpected_error_mid_stream_becomes_an_error_event(client, monkeypatch):
    def broken_stream(self, *args):
        raise RuntimeError("boom")
        yield  # pragma: no cover

    monkeypatch.setattr(TriageService, "stream", broken_stream)

    events = read_sse(_stream_generate(client))

    assert _names(events) == ["start", "error"]
    assert events[1][1]["error"]["code"] == "internal_error"
    assert events[1][1]["request_id"]


def test_compare_streams_every_model_then_a_votable_comparison(client, sonnet, haiku):
    sonnet.replies.append(analysis_json(summary="sonnet"))
    haiku.replies.append(analysis_json(summary="haiku"))

    events = read_sse(_stream_compare(client, [SONNET, HAIKU]))

    assert [m["id"] for m in events[0][1]["models"]] == [SONNET, HAIKU]
    assert {data["model"] for name, data in events if name == "delta"} == {SONNET, HAIKU}
    results = {data["model"]: data for name, data in events if name == "result"}
    assert results[SONNET]["analysis"]["summary"] == "sonnet"
    assert results[HAIKU]["analysis"]["summary"] == "haiku"

    done = events[-1][1]
    assert events[-1][0] == "done"
    vote = client.post(f"/api/comparisons/{done['comparison_id']}/vote", json={"model": HAIKU})
    assert vote.status_code == 200


def test_compare_stream_with_one_failure(client, sonnet, haiku):
    sonnet.replies.append(analysis_json())
    haiku.replies.append("not json")

    events = read_sse(_stream_compare(client, [SONNET, HAIKU]))

    results = {data["model"]: data for name, data in events if name == "result"}
    assert results[SONNET]["ok"] is True
    assert results[HAIKU]["error"]["code"] == "model_output_invalid"
    assert events[-1][1]["comparison_id"] is not None


def test_compare_stream_where_every_model_fails_saves_no_comparison(client, sonnet, haiku):
    sonnet.replies.append("not json")
    haiku.replies.append("not json")

    events = read_sse(_stream_compare(client, [SONNET, HAIKU]))

    assert events[-1] == ("done", {"conversation_id": events[0][1]["conversation_id"], "comparison_id": None})
    assert client.get("/api/comparisons/stats").get_json() == {"models": []}


def test_client_disconnect_stops_the_model_stream(client, sonnet):
    sonnet.replies.append(analysis_json(summary="x" * 2000))  # ~250 chunks

    response = client.post("/api/generate", json={"message": "hi", "stream": True}, buffered=False)
    body = iter(response.response)
    next(body)  # "start"
    next(body)  # first delta
    response.close()  # the client goes away

    assert sonnet.chunks_sent < 50
    # Nothing was recorded: asking again is not a cache hit.
    sonnet.replies.append(analysis_json())
    assert client.post("/api/generate", json={"message": "hi"}).get_json()["result"]["cached"] is False
