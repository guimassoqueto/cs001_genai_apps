import logging

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException, InternalServerError

from genai_app.exceptions import AppError
from genai_app.logs import get_request_id

logger = logging.getLogger(__name__)


def error_response(code: str, message: str, status: int):
    return jsonify(error={"code": code, "message": message}, request_id=get_request_id()), status


def _is_api_request() -> bool:
    return request.blueprint == "api" or request.path.startswith("/api/")


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(AppError)
    def app_error(error: AppError):
        log = logger.warning if error.status >= 500 else logger.info
        log("%s %s -> %s %s: %s", request.method, request.path, error.status, error.code, error.message)
        return error_response(error.code, error.message, error.status)

    @app.errorhandler(HTTPException)
    def http_error(error: HTTPException):
        # JSON for the API, Flask's default HTML pages everywhere else.
        if not _is_api_request():
            return error
        code = error.name.lower().replace(" ", "_")
        return error_response(code, error.description or error.name, error.code or 500)

    @app.errorhandler(Exception)
    def unexpected_error(error: Exception):
        logger.exception("Unhandled error on %s %s", request.method, request.path)
        if not _is_api_request():
            return InternalServerError()
        return error_response(AppError.code, AppError.message, 500)
