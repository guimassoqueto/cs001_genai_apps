"""Application errors.

Each carries the HTTP status, a stable machine-readable code and a message that is safe
to show to the user. The error handlers turn them into
{"error": {"code": ..., "message": ...}, "request_id": ...}.
"""


class AppError(Exception):
    status = 500
    code = "internal_error"
    message = "Internal server error."

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.message
        super().__init__(self.message)

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


class InvalidRequest(AppError):
    status = 400
    code = "invalid_request"
    message = "The request is invalid."


class NotFound(AppError):
    status = 404
    code = "not_found"
    message = "Not found."


# --- Model output -------------------------------------------------------------


class ModelOutputInvalid(AppError):
    status = 502
    code = "model_output_invalid"
    message = "The model reply did not match the expected format."


class ModelOutputTruncated(ModelOutputInvalid):
    code = "model_output_truncated"
    message = "The model reply was cut off at the token limit. Raise ANTHROPIC_MAX_TOKENS."


class ModelRefused(ModelOutputInvalid):
    code = "model_refused"
    message = "The model declined to answer this message."


# --- Anthropic API --------------------------------------------------------------


class UpstreamError(AppError):
    status = 502
    code = "upstream_error"
    message = "The Anthropic API returned an error."


class UpstreamAuthError(UpstreamError):
    code = "upstream_auth"
    message = "The Anthropic API rejected the API key. Check ANTHROPIC_API_KEY."


class ModelNotAvailable(UpstreamError):
    code = "model_not_available"
    message = "This model is not available for the configured API key."


class UpstreamRateLimited(UpstreamError):
    status = 429
    code = "upstream_rate_limited"
    message = "The Anthropic API rate limit was reached. Try again in a moment."


class UpstreamUnavailable(UpstreamError):
    status = 503
    code = "upstream_unavailable"
    message = "The Anthropic API is unavailable or overloaded. Try again shortly."


class UpstreamTimeout(UpstreamError):
    status = 504
    code = "upstream_timeout"
    message = "The Anthropic API took too long to answer."


class StreamCancelled(AppError):
    """The client went away mid-stream, so the model call was abandoned."""

    status = 499
    code = "cancelled"
    message = "The request was cancelled."
