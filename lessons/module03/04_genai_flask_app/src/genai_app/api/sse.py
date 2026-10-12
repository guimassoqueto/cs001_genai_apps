"""Server-Sent Events: the wire format for streamed answers.

Each event is `event: <name>\\ndata: <one line of JSON>\\n\\n`, the same framing the OpenAI and
Anthropic streaming APIs use. Browsers read it with fetch() + a stream reader (EventSource
cannot POST).
"""

import json
import logging
from collections.abc import Iterator
from typing import Any

from flask import Response, stream_with_context
from pydantic import BaseModel

from genai_app.exceptions import AppError
from genai_app.logs import get_request_id, request_id_var

logger = logging.getLogger(__name__)


def sse(event: str, data: BaseModel | dict[str, Any]) -> str:
    """Format one event. JSON is always a single line, so one `data:` field is enough."""
    payload = data.model_dump_json() if isinstance(data, BaseModel) else json.dumps(data, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"


def sse_response(events: Iterator[str]) -> Response:
    """Stream `events` to the client.

    An error after the stream has started can no longer change the HTTP status, so it is sent
    as a final `error` event with the same body as a JSON error response.
    """
    request_id = get_request_id()

    def guarded() -> Iterator[str]:
        # The body is sent after the request hooks ran: re-bind the request id for log lines.
        token = request_id_var.set(request_id)
        try:
            yield from events
        except AppError as error:
            yield sse("error", {"error": error.to_dict(), "request_id": request_id})
        except Exception:
            logger.exception("Stream failed")
            yield sse("error", {"error": AppError().to_dict(), "request_id": request_id})
        finally:
            request_id_var.reset(token)

    return Response(
        stream_with_context(guarded()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # tell nginx-style proxies not to buffer the stream
        },
    )
