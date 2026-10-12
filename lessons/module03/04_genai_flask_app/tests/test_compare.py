import uuid

import pytest
from langchain_core.messages import AIMessage

from tests.conftest import HAIKU, OPUS, SONNET, analysis_json


def _compare(client, models, message="I was charged twice!"):
    return client.post("/api/compare", json={"message": message, "models": models})


def test_compare_returns_one_result_per_model_in_order(client, sonnet, haiku):
    sonnet.replies.append(analysis_json(summary="sonnet"))
    usage = {"input_tokens": 9, "output_tokens": 3, "total_tokens": 12}
    haiku.replies.append(AIMessage(analysis_json(summary="haiku"), usage_metadata=usage))

    response = _compare(client, [HAIKU, SONNET])

    assert response.status_code == 200
    body = response.get_json()
    uuid.UUID(body["comparison_id"])
    assert [r["model"] for r in body["results"]] == [HAIKU, SONNET]
    assert [r["analysis"]["summary"] for r in body["results"]] == ["haiku", "sonnet"]
    assert body["results"][0]["usage"] == {"input_tokens": 9, "output_tokens": 3}


def test_one_failing_model_does_not_fail_the_comparison(client, sonnet, haiku):
    sonnet.replies.append(analysis_json())
    haiku.replies.append("not json")

    response = _compare(client, [SONNET, HAIKU])

    assert response.status_code == 200
    sonnet_result, haiku_result = response.get_json()["results"]
    assert sonnet_result["ok"] is True
    assert haiku_result["ok"] is False
    assert haiku_result["analysis"] is None
    assert haiku_result["error"]["code"] == "model_output_invalid"


def test_all_models_failing_is_an_error(client, sonnet, haiku):
    sonnet.replies.append(AIMessage("{", response_metadata={"stop_reason": "max_tokens"}))
    haiku.replies.append("not json")

    response = _compare(client, [SONNET, HAIKU])

    assert response.status_code == 502
    assert response.get_json()["error"]["code"] == "model_output_truncated"


@pytest.mark.parametrize(
    "models",
    [[SONNET], [SONNET, SONNET], [SONNET, "gpt-4"], []],
)
def test_compare_rejects_bad_model_lists(client, models):
    response = _compare(client, models)

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_request"


def test_vote_and_stats(client, sonnet, haiku, opus):
    sonnet.replies += [analysis_json(), analysis_json()]
    haiku.replies += [analysis_json(), "not json"]
    opus.replies.append(analysis_json())

    first = _compare(client, [SONNET, HAIKU], "message one").get_json()["comparison_id"]
    second = _compare(client, [SONNET, HAIKU, OPUS], "message two").get_json()["comparison_id"]

    assert client.post(f"/api/comparisons/{first}/vote", json={"model": HAIKU}).status_code == 200
    assert client.post(f"/api/comparisons/{second}/vote", json={"model": OPUS}).status_code == 200

    stats = {row["model"]: row for row in client.get("/api/comparisons/stats").get_json()["models"]}
    assert stats[HAIKU] | {"avg_duration": None} == {
        "model": HAIKU,
        "label": "Claude Haiku 5.5",
        "runs": 2,
        "errors": 1,
        "votes": 2,
        "wins": 1,
        "win_rate": 0.5,
        "avg_duration": None,
        "avg_output_tokens": None,
    }
    assert stats[SONNET]["wins"] == 0
    assert stats[SONNET]["win_rate"] == 0
    assert stats[OPUS]["runs"] == 1
    assert stats[OPUS]["win_rate"] == 1


def test_vote_can_be_changed(client, sonnet, haiku):
    sonnet.replies.append(analysis_json())
    haiku.replies.append(analysis_json())
    comparison = _compare(client, [SONNET, HAIKU]).get_json()["comparison_id"]

    client.post(f"/api/comparisons/{comparison}/vote", json={"model": SONNET})
    client.post(f"/api/comparisons/{comparison}/vote", json={"model": HAIKU})

    stats = {row["model"]: row for row in client.get("/api/comparisons/stats").get_json()["models"]}
    assert (stats[SONNET]["wins"], stats[HAIKU]["wins"]) == (0, 1)


def test_cannot_vote_for_a_failed_or_absent_model(client, sonnet, haiku):
    sonnet.replies.append(analysis_json())
    haiku.replies.append("not json")
    comparison = _compare(client, [SONNET, HAIKU]).get_json()["comparison_id"]

    failed = client.post(f"/api/comparisons/{comparison}/vote", json={"model": HAIKU})
    absent = client.post(f"/api/comparisons/{comparison}/vote", json={"model": OPUS})

    assert failed.status_code == 400
    assert absent.status_code == 400


def test_vote_on_unknown_comparison_is_404(client):
    response = client.post(f"/api/comparisons/{uuid.uuid4()}/vote", json={"model": SONNET})

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "not_found"


def test_stats_start_empty(client):
    assert client.get("/api/comparisons/stats").get_json() == {"models": []}
