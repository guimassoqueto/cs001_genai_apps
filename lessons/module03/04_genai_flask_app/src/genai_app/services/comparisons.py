import sqlite3
import uuid

from genai_app.exceptions import InvalidRequest, NotFound
from genai_app.services.triage import ModelResult


class ComparisonStore:
    """A/B test runs, the user's preferred model for each, and per-model aggregates."""

    def __init__(self, db: sqlite3.Connection) -> None:
        self.db = db

    def create(self, conversation_id: str, results: list[ModelResult]) -> str:
        comparison_id = str(uuid.uuid4())
        with self.db:
            self.db.execute(
                "INSERT INTO comparisons (id, conversation_id) VALUES (?, ?)", (comparison_id, conversation_id)
            )
            self.db.executemany(
                """
                INSERT INTO comparison_results
                    (comparison_id, model, ok, error_code, duration, cached, input_tokens, output_tokens)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        comparison_id,
                        r.model,
                        r.ok,
                        r.error.code if r.error else None,
                        r.duration,
                        r.cached,
                        r.reply.usage.input_tokens if r.ok and r.reply.usage else None,
                        r.reply.usage.output_tokens if r.ok and r.reply.usage else None,
                    )
                    for r in results
                ],
            )
        return comparison_id

    def vote(self, comparison_id: str, model_id: str) -> None:
        """Record (or change) which model's answer the user preferred."""
        if self.db.execute("SELECT 1 FROM comparisons WHERE id = ?", (comparison_id,)).fetchone() is None:
            raise NotFound("Comparison not found.")
        result = self.db.execute(
            "SELECT ok FROM comparison_results WHERE comparison_id = ? AND model = ?", (comparison_id, model_id)
        ).fetchone()
        if result is None or not result["ok"]:
            raise InvalidRequest(f"'{model_id}' has no successful answer in this comparison.")
        with self.db:
            self.db.execute(
                "UPDATE comparisons SET winner = ?, voted_at = CURRENT_TIMESTAMP WHERE id = ?",
                (model_id, comparison_id),
            )

    def stats(self) -> list[dict]:
        """Per model: runs, errors, wins, win rate (over voted runs it took part in), mean latency and output tokens.

        Latency and tokens only count real calls, not cache hits.
        """
        rows = self.db.execute(
            """
            SELECT r.model,
                   COUNT(*)                                                     AS runs,
                   SUM(1 - r.ok)                                                AS errors,
                   SUM(c.winner IS NOT NULL)                                    AS voted,
                   SUM(c.winner = r.model)                                      AS wins,
                   AVG(CASE WHEN r.ok AND NOT r.cached THEN r.duration END)      AS avg_duration,
                   AVG(CASE WHEN r.ok AND NOT r.cached THEN r.output_tokens END) AS avg_output_tokens
            FROM comparison_results r
            JOIN comparisons c ON c.id = r.comparison_id
            GROUP BY r.model
            ORDER BY wins DESC, avg_duration
            """
        ).fetchall()
        return [
            {
                "model": row["model"],
                "runs": row["runs"],
                "errors": row["errors"],
                "votes": row["voted"],
                "wins": row["wins"],
                "win_rate": round(row["wins"] / row["voted"], 3) if row["voted"] else None,
                "avg_duration": round(row["avg_duration"], 3) if row["avg_duration"] is not None else None,
                "avg_output_tokens": round(row["avg_output_tokens"]) if row["avg_output_tokens"] is not None else None,
            }
            for row in rows
        ]
