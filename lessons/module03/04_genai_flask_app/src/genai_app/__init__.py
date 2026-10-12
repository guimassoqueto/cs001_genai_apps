from flask import Flask
from langchain_core.language_models import BaseChatModel

from genai_app.api import bp as api_bp
from genai_app.cli import register_cli
from genai_app.config import Config
from genai_app.errors import register_error_handlers
from genai_app.services.assistant import InquiryAssistant, build_chat_model
from genai_app.web import bp as web_bp


def create_app(config: Config | None = None, *, chat_model: BaseChatModel | None = None) -> Flask:
    """Application factory.

    Args:
        config: settings object; defaults to Config(), read from the environment and .env.
        chat_model: model to use instead of ChatAnthropic. Tests pass a fake one here.
    """
    app = Flask(__name__)
    app.config.from_object(config or Config())

    if chat_model is None:
        if not app.config["ANTHROPIC_API_KEY"]:
            raise RuntimeError("ANTHROPIC_API_KEY is not set. Run 'make env' and fill in .env.")
        chat_model = build_chat_model(app)
    app.extensions["assistant"] = InquiryAssistant(chat_model, model_name=app.config["ANTHROPIC_MODEL"])

    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp, url_prefix="/api")
    register_error_handlers(app)
    register_cli(app)

    return app
