import sqlite3
from importlib.resources import files
from pathlib import Path

from flask import Flask, current_app, g


def get_db() -> sqlite3.Connection:
    """Return this request's SQLite connection, opening it on first use."""
    if "db" not in g:
        g.db = _connect(current_app.config["DATABASE"])
    return g.db


def close_db(_exc: BaseException | None = None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app: Flask) -> None:
    """Create the database file and tables if they do not exist yet."""
    path = Path(app.config["DATABASE"])
    path.parent.mkdir(parents=True, exist_ok=True)
    db = _connect(str(path))
    try:
        db.execute("PRAGMA journal_mode = WAL")  # readers do not block the writer (several gunicorn workers)
        db.executescript(files("genai_app").joinpath("schema.sql").read_text())
    finally:
        db.close()
    app.teardown_appcontext(close_db)


def _connect(path: str) -> sqlite3.Connection:
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db
