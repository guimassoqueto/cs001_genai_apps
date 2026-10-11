import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

API_KEY_ENV_VAR = "ANTHROPIC_API_KEY"

DEFAULT_MODEL = "claude-sonnet-5-5"
DEFAULT_MAX_TOKENS = 1024

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LESSONS_DIR = PROJECT_ROOT / "lessons"


def get_api_key() -> str:
    """Return the Anthropic API key.

    Raises:
        RuntimeError: if the key is not set in the environment or in .env.
    """
    api_key = os.getenv(API_KEY_ENV_VAR)
    if not api_key:
        raise RuntimeError(f"{API_KEY_ENV_VAR} is not set. Run 'make env' and fill in .env.")
    return api_key


def doc_path(script: str) -> Path:
    """Return the notes a lesson was written from: the .md file beside the script.

    lessons/module02/01_langchain_core_concepts.py
        -> lessons/module02/01_langchain_core_concepts.md

    Args:
        script: the calling script's __file__.
    """
    return Path(script).resolve().with_suffix(".md")


def output_path(script: str, filename: str) -> Path:
    """Return the path a lesson should write a generated file to.

    lessons/module02/01_langchain_core_concepts.py + "concepts.json"
        -> lessons/module02/output/01_langchain_core_concepts/concepts.json

    The parent directory is created if needed, so callers can write immediately.

    Args:
        script: the calling script's __file__.
        filename: name of the file to generate.
    """
    lesson = Path(script).resolve()
    path = lesson.parent / "output" / lesson.stem / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
