from collections.abc import Mapping

from flask import Flask
from langchain_core.language_models import BaseChatModel

from genai_app.api import bp as api_bp
from genai_app.cli import register_cli
from genai_app.config import Config
from genai_app.db import init_db
from genai_app.errors import register_error_handlers
from genai_app.extensions import cache
from genai_app.logs import configure_logging, init_request_logging
from genai_app.services.assistant import InquiryAssistant, build_chat_models
from genai_app.web import bp as web_bp


def create_app(config: Config | None = None, *, chat_models: Mapping[str, BaseChatModel] | None = None) -> Flask:
    """Application factory.

    Args:
        config: settings object; defaults to Config(), read from the environment and .env.
        chat_models: model id -> chat model, used instead of ChatAnthropic. Tests pass fakes here.
    """
    config = config or Config()
    configure_logging(config.LOG_LEVEL)

    app = Flask(__name__)
    app.config.from_object(config)
    _check_model_config(app)

    if chat_models is None:
        if not app.config["ANTHROPIC_API_KEY"]:
            raise RuntimeError("ANTHROPIC_API_KEY is not set. Run 'make env' and fill in .env.")
        chat_models = build_chat_models(app)
    app.extensions["assistant"] = InquiryAssistant(chat_models)

    cache.init_app(app)
    init_db(app)
    init_request_logging(app)

    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp, url_prefix="/api")
    register_error_handlers(app)
    register_cli(app)

    app.logger.info(
        "Ready with models: %s (default %s)", ", ".join(app.config["ANTHROPIC_MODELS"]), app.config["ANTHROPIC_MODEL"]
    )
    return app


def _check_model_config(app: Flask) -> None:
    models = app.config["ANTHROPIC_MODELS"]
    if not models:
        raise RuntimeError("ANTHROPIC_MODELS is empty. List at least one model id.")
    if app.config["ANTHROPIC_MODEL"] not in models:
        raise RuntimeError(f"ANTHROPIC_MODEL={app.config['ANTHROPIC_MODEL']} is not in ANTHROPIC_MODELS ({models}).")
