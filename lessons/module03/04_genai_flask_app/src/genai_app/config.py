import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parents[2]

# Explicit path: never pick up a .env from a parent directory.
load_dotenv(PROJECT_DIR / ".env")


class Config:
    """Settings read from the environment when the app is created."""

    TESTING = False

    # Flask rejects request bodies larger than this with 413.
    MAX_CONTENT_LENGTH = 16 * 1024
    MAX_MESSAGE_CHARS = 4000

    def __init__(self) -> None:
        self.ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
        self.ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5")
        # Adaptive thinking tokens count against this limit, so leave headroom for the JSON answer.
        self.ANTHROPIC_MAX_TOKENS = int(os.environ.get("ANTHROPIC_MAX_TOKENS", "2048"))
        self.ANTHROPIC_TIMEOUT = float(os.environ.get("ANTHROPIC_TIMEOUT", "60"))


class TestingConfig(Config):
    TESTING = True

    def __init__(self) -> None:
        super().__init__()
        self.ANTHROPIC_API_KEY = "test-key"
