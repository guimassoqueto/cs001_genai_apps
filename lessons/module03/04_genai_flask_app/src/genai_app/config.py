import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parents[2]

# Explicit path: never pick up a .env from a parent directory.
load_dotenv(PROJECT_DIR / ".env")

DEFAULT_MODELS = "claude-opus-5-5,claude-fable-5-1,claude-sonnet-5-5,claude-haiku-5-5"


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


class Config:
    """Settings read from the environment when the app is created."""

    TESTING = False

    # Flask rejects request bodies larger than this with 413.
    MAX_CONTENT_LENGTH = 16 * 1024

    def __init__(self) -> None:
        env = os.environ.get

        # Models
        self.ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", "")
        self.ANTHROPIC_MODELS = _csv(env("ANTHROPIC_MODELS", DEFAULT_MODELS))
        self.ANTHROPIC_MODEL = env("ANTHROPIC_MODEL", "claude-sonnet-5-5")
        # Adaptive thinking tokens count against this limit, so leave headroom for the JSON answer.
        self.ANTHROPIC_MAX_TOKENS = int(env("ANTHROPIC_MAX_TOKENS", "2048"))
        self.ANTHROPIC_TIMEOUT = float(env("ANTHROPIC_TIMEOUT", "120"))
        # The Anthropic SDK retries connection errors, 429 and 5xx with backoff.
        self.ANTHROPIC_MAX_RETRIES = int(env("ANTHROPIC_MAX_RETRIES", "2"))

        # Conversation memory: how many earlier turns each model sees.
        self.MEMORY_MAX_TURNS = int(env("MEMORY_MAX_TURNS", "10"))

        # Response cache (Flask-Caching). NullCache disables it; RedisCache shares it between workers.
        self.CACHE_TYPE = env("CACHE_TYPE", "SimpleCache")
        self.CACHE_DEFAULT_TIMEOUT = int(env("CACHE_DEFAULT_TIMEOUT", "3600"))
        self.CACHE_THRESHOLD = int(env("CACHE_THRESHOLD", "500"))
        self.CACHE_REDIS_URL = env("CACHE_REDIS_URL", "")

        # SQLite file for conversation memory and A/B test results.
        self.DATABASE = env("DATABASE", str(PROJECT_DIR / "instance" / "genai_app.sqlite3"))

        self.LOG_LEVEL = env("LOG_LEVEL", "INFO").upper()


class TestingConfig(Config):
    TESTING = True

    def __init__(self, database: str) -> None:
        super().__init__()
        self.ANTHROPIC_API_KEY = "test-key"
        self.ANTHROPIC_MODELS = _csv(DEFAULT_MODELS)
        self.ANTHROPIC_MODEL = "claude-sonnet-5-5"
        self.MEMORY_MAX_TURNS = 10
        self.CACHE_TYPE = "SimpleCache"
        self.DATABASE = database
        self.LOG_LEVEL = "WARNING"
