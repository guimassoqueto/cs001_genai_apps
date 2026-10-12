from collections.abc import Callable, Iterator

from genai_app.api.schemas import ModelRef, ModelResultOut, StreamDelta, StreamDone, StreamStart
from genai_app.api.sse import sse
from genai_app.services.catalog import model_info
from genai_app.services.triage import ModelDelta, ModelFinished, ModelResult, RunCompleted, TriageService

# Called once every model is done; returns the comparison id to report, if any.
OnCompleted = Callable[[list[ModelResult]], str | None]


def triage_events(
    triage_factory: Callable[[], TriageService],
    message: str,
    model_ids: list[str],
    conversation_id: str,
    on_completed: OnCompleted | None = None,
) -> Iterator[str]:
    """Translate a TriageService stream into SSE events: start, delta*, result+, done.

    The service is created lazily, once the response body starts streaming, so it uses
    resources (the database connection) that are valid for the whole stream.
    """
    yield sse(
        "start",
        StreamStart(
            conversation_id=conversation_id,
            models=[ModelRef(id=m, label=model_info(m).label) for m in model_ids],
        ),
    )

    for event in triage_factory().stream(message, model_ids, conversation_id):
        match event:
            case ModelDelta(model=model, text=text, partial=partial):
                yield sse("delta", StreamDelta(model=model, text=text, partial=partial))
            case ModelFinished(result=result):
                yield sse("result", ModelResultOut.from_result(result))
            case RunCompleted(results=results):
                comparison_id = on_completed(results) if on_completed else None
                yield sse("done", StreamDone(conversation_id=conversation_id, comparison_id=comparison_id))
