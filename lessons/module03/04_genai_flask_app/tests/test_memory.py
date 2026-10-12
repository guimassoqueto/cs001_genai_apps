import json

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from tests.conftest import HAIKU, OPUS, analysis_json


def _send(client, message, conversation_id=None, model=None):
    payload = {"message": message}
    if conversation_id:
        payload["conversation_id"] = conversation_id
    if model:
        payload["model"] = model
    response = client.post("/api/generate", json=payload)
    assert response.status_code == 200, response.get_json()
    return response.get_json()["conversation_id"]


def test_first_message_has_no_history(client, sonnet):
    sonnet.replies.append(analysis_json())

    _send(client, "My order #123 is late")

    [prompt] = sonnet.calls
    assert [type(m) for m in prompt] == [SystemMessage, HumanMessage]


def test_follow_up_sees_the_earlier_turns(client, sonnet):
    sonnet.replies += [analysis_json(summary="late order"), analysis_json()]

    conversation = _send(client, "My order #123 is late")
    _send(client, "Also I was charged twice for it", conversation)

    prompt = sonnet.calls[1]
    assert [type(m) for m in prompt] == [SystemMessage, HumanMessage, AIMessage, HumanMessage]
    assert prompt[1].content == "My order #123 is late"
    assert json.loads(prompt[2].content)["summary"] == "late order"
    assert prompt[3].content == "Also I was charged twice for it"


def test_new_conversation_starts_empty(client, sonnet):
    sonnet.replies += [analysis_json(), analysis_json(summary="other")]

    _send(client, "My order #123 is late")
    _send(client, "Something else entirely")

    assert len(sonnet.calls[1]) == 2


def test_history_is_capped_at_max_turns(app, client, sonnet):
    app.config["MEMORY_MAX_TURNS"] = 2
    sonnet.replies += [analysis_json(summary=f"turn {i}") for i in range(4)]

    conversation = _send(client, "turn 0")
    for i in range(1, 4):
        _send(client, f"turn {i}", conversation)

    prompt = sonnet.calls[3]
    assert [m.content for m in prompt if isinstance(m, HumanMessage)] == ["turn 1", "turn 2", "turn 3"]


def test_clearing_a_conversation_forgets_it(client, sonnet):
    sonnet.replies += [analysis_json(), analysis_json(summary="fresh")]

    conversation = _send(client, "My order #123 is late")
    assert client.delete(f"/api/conversations/{conversation}").status_code == 204
    _send(client, "What was my order number?", conversation)

    assert len(sonnet.calls[1]) == 2


def test_switching_model_keeps_the_context(client, sonnet, haiku):
    sonnet.replies.append(analysis_json(summary="from sonnet"))
    haiku.replies.append(analysis_json())

    conversation = _send(client, "My order #123 is late")
    _send(client, "Any update?", conversation, model=HAIKU)

    prompt = haiku.calls[0]
    assert json.loads(prompt[2].content)["summary"] == "from sonnet"


def test_after_an_ab_turn_each_model_sees_its_own_answer(client, sonnet, haiku, opus):
    sonnet.replies += [analysis_json(summary="sonnet says"), analysis_json()]
    haiku.replies += [analysis_json(summary="haiku says"), analysis_json()]
    opus.replies.append(analysis_json())

    compare = client.post("/api/compare", json={"message": "My order is late", "models": ["claude-sonnet-5-5", HAIKU]})
    conversation = compare.get_json()["conversation_id"]
    _send(client, "Any update?", conversation)
    _send(client, "Any update?", conversation, model=HAIKU)
    _send(client, "Any update?", conversation, model=OPUS)

    assert json.loads(sonnet.calls[1][2].content)["summary"] == "sonnet says"
    assert json.loads(haiku.calls[1][2].content)["summary"] == "haiku says"
    # Opus was not in the A/B turn: it gets the first answer recorded for that turn.
    assert json.loads(opus.calls[0][2].content)["summary"] == "sonnet says"


def test_failed_turns_are_not_remembered(client, sonnet):
    sonnet.replies += ["not json", analysis_json()]

    first = client.post("/api/generate", json={"message": "garbled"})
    assert first.status_code == 502
    _send(client, "hello")

    assert len(sonnet.calls[1]) == 2
