import json

import click
from flask import Flask, current_app

from genai_app.services.assistant import get_assistant


def register_cli(app: Flask) -> None:
    @app.cli.command("ask")
    @click.argument("message")
    @click.option("--model", "-m", "models", multiple=True, help="Model id; repeat to ask several. Default: all.")
    def ask(message: str, models: tuple[str, ...]) -> None:
        """Analyze MESSAGE and print the JSON result per model (makes billed API calls, no cache or memory)."""
        assistant = get_assistant(current_app)
        for model_id in models or assistant.model_ids:
            reply = assistant.analyze(model_id, message)
            click.echo(f"# {model_id}")
            click.echo(json.dumps(reply.analysis.model_dump(), indent=2))
