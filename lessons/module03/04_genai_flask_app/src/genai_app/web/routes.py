from flask import current_app, render_template

from genai_app.api.schemas import MAX_MESSAGE_CHARS
from genai_app.services.assistant import get_assistant
from genai_app.web import bp


@bp.get("/")
def index():
    return render_template(
        "index.html",
        model_name=get_assistant(current_app).model_name,
        max_message_chars=MAX_MESSAGE_CHARS,
    )
