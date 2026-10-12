import json
import sqlite3

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage


class ConversationMemory:
    """Conversation history stored in SQLite and replayed to the model as chat messages.

    One turn = one user message + the analysis each model returned for it. When a model
    asks for the history it gets its own earlier answers where it has one (A/B turns), and
    otherwise the answer the user saw (turns answered by a different model).
    """

    def __init__(self, db: sqlite3.Connection, max_turns: int) -> None:
        self.db = db
        self.max_turns = max_turns

    def history(self, conversation_id: str, model_id: str) -> list[BaseMessage]:
        rows = self.db.execute(
            """
            SELECT user_message, replies FROM (
                SELECT id, user_message, replies FROM conversation_turns
                WHERE conversation_id = ? ORDER BY id DESC LIMIT ?
            ) ORDER BY id
            """,
            (conversation_id, self.max_turns),
        ).fetchall()

        messages: list[BaseMessage] = []
        for row in rows:
            replies: dict[str, str] = json.loads(row["replies"])
            reply = replies.get(model_id) or next(iter(replies.values()))
            messages += [HumanMessage(row["user_message"]), AIMessage(reply)]
        return messages

    def record(self, conversation_id: str, user_message: str, replies: dict[str, str]) -> None:
        """Store a turn. `replies` maps model id -> that model's analysis as JSON; it must not be empty."""
        with self.db:
            self.db.execute(
                "INSERT INTO conversation_turns (conversation_id, user_message, replies) VALUES (?, ?, ?)",
                (conversation_id, user_message, json.dumps(replies)),
            )

    def clear(self, conversation_id: str) -> int:
        with self.db:
            cursor = self.db.execute("DELETE FROM conversation_turns WHERE conversation_id = ?", (conversation_id,))
        return cursor.rowcount
