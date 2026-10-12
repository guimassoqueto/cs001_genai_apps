import time

from flask import current_app, jsonify, request
from pydantic import ValidationError

from genai_app.api import bp
from genai_app.api.schemas import GenerateRequest, GenerateResponse
from genai_app.errors import error_response
from genai_app.services.assistant import get_assistant


@bp.get("/health")
def health():
    return jsonify(status="ok", model=get_assistant(current_app).model_name)


@bp.post("/generate")
def generate():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return error_response(400, "Request body must be a JSON object.")

    try:
        payload = GenerateRequest.model_validate(body)
    except ValidationError as exc:
        details = "; ".join(f"{'.'.join(map(str, e['loc'])) or 'body'}: {e['msg']}" for e in exc.errors())
        return error_response(400, details)

    assistant = get_assistant(current_app)
    start = time.perf_counter()
    analysis = assistant.analyze(payload.message)
    duration = time.perf_counter() - start

    response = GenerateResponse(analysis=analysis, model=assistant.model_name, duration=round(duration, 3))
    return jsonify(response.model_dump())
