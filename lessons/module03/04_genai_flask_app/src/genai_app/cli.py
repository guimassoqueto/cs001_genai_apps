import json

import click
from flask import Flask, current_app

from genai_app.services.assistant import get_assistant


def register_cli(app: Flask) -> None:
    @app.cli.command("ask")
    @click.argument("message")
    def ask(message: str) -> None:
        """Analyze MESSAGE with the model and print the JSON result (makes a billed API call)."""
        analysis = get_assistant(current_app).analyze(message)
        click.echo(json.dumps(analysis.model_dump(), indent=2))
