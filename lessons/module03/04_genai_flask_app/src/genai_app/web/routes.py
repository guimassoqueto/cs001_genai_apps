import uuid

from flask import current_app, render_template

from genai_app.api.schemas import MAX_MESSAGE_CHARS
from genai_app.services.catalog import model_info
from genai_app.web import bp

# Builds URLs for routes that take an id; the frontend swaps it for the real one.
ID_PLACEHOLDER = uuid.UUID(int=0)


@bp.get("/")
def index():
    models = [model_info(model_id) for model_id in current_app.config["ANTHROPIC_MODELS"]]
    return render_template(
        "index.html",
        models=models,
        models_json=[{"id": m.id, "label": m.label} for m in models],
        default_model=current_app.config["ANTHROPIC_MODEL"],
        max_message_chars=MAX_MESSAGE_CHARS,
        id_placeholder=ID_PLACEHOLDER,
    )
