import anthropic
from flask import Flask, jsonify, request
from langchain_core.exceptions import OutputParserException
from werkzeug.exceptions import HTTPException


def error_response(status: int, message: str):
    return jsonify(error=message), status


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(OutputParserException)
    def model_output_invalid(exc: OutputParserException):
        app.logger.warning("Model output did not match the schema: %s", exc)
        return error_response(
            502,
            "The model reply could not be parsed. If it was cut off, raise ANTHROPIC_MAX_TOKENS.",
        )

    @app.errorhandler(anthropic.APIStatusError)
    def anthropic_status_error(exc: anthropic.APIStatusError):
        app.logger.error("Anthropic API returned %s: %s", exc.status_code, exc.message)
        return error_response(502, f"The Anthropic API returned an error ({exc.status_code}).")

    @app.errorhandler(anthropic.APIConnectionError)
    def anthropic_connection_error(exc: anthropic.APIConnectionError):
        app.logger.error("Could not reach the Anthropic API: %s", exc)
        return error_response(503, "Could not reach the Anthropic API. Try again shortly.")

    @app.errorhandler(HTTPException)
    def http_error(exc: HTTPException):
        # JSON for the API, Flask's default HTML pages everywhere else.
        if request.blueprint == "api" or request.path.startswith("/api/"):
            return error_response(exc.code or 500, exc.description or exc.name)
        return exc

    @app.errorhandler(Exception)
    def unexpected_error(exc: Exception):
        app.logger.exception("Unhandled error")
        return error_response(500, "Internal server error.")
