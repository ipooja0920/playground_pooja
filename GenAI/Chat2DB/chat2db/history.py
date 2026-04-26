"""
Persistent chat history manager — stores sessions, saved queries, and favorites
in ~/.chat2db/history.json so history survives across Streamlit restarts.
"""

import decimal
import json
import uuid
from datetime import datetime
from pathlib import Path

HISTORY_DIR = Path.home() / ".chat2db"
HISTORY_FILE = HISTORY_DIR / "history.json"


def _serialise(obj):
    """Recursively convert non-JSON-serialisable types so the file never breaks."""
    if isinstance(obj, dict):
        return {k: _serialise(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialise(v) for v in obj]
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj


class HistoryManager:
    """Read / write chat history to a local JSON file."""

    def __init__(self):
        HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _load(self) -> dict:
        if HISTORY_FILE.exists():
            try:
                return json.loads(HISTORY_FILE.read_text())
            except Exception:
                pass
        return {"sessions": [], "saved": [], "favorites": []}

    def _flush(self):
        HISTORY_FILE.write_text(
            json.dumps(_serialise(self._data), indent=2, default=str)
        )

    # ── Sessions ──────────────────────────────────────────────────────────────

    def upsert_session(
        self,
        session_id: str,
        messages: list,
        message_meta: dict,
        previous_sql: str = "",
    ):
        """Save or update a chat session. Title = first user message (truncated)."""
        user_msgs = [m for m in messages if m.get("role") == "user"]
        title = user_msgs[0]["content"][:60] if user_msgs else "Untitled"

        entry = {
            "id": session_id,
            "title": title,
            "messages": messages,
            "message_meta": {str(k): v for k, v in message_meta.items()},
            "previous_sql": previous_sql,
            "updated_at": datetime.now().isoformat(),
        }
        sessions = self._data["sessions"]
        for i, s in enumerate(sessions):
            if s["id"] == session_id:
                sessions[i] = entry
                self._flush()
                return
        sessions.insert(0, entry)
        self._data["sessions"] = sessions[:100]
        self._flush()

    def get_recent(self, n: int = 5) -> list:
        return self._data["sessions"][:n]

    def get_session(self, session_id: str) -> dict | None:
        for s in self._data["sessions"]:
            if s["id"] == session_id:
                return s
        return None

    def delete_session(self, session_id: str):
        self._data["sessions"] = [
            s for s in self._data["sessions"] if s["id"] != session_id
        ]
        self._flush()

    # ── Saved queries ─────────────────────────────────────────────────────────

    def save_query(self, question: str, sql: str, answer: str) -> str:
        """Bookmark a query. Returns its new ID."""
        entry = {
            "id": str(uuid.uuid4()),
            "question": question,
            "sql": sql,
            "answer": answer,
            "saved_at": datetime.now().isoformat(),
        }
        self._data["saved"].insert(0, entry)
        self._data["saved"] = self._data["saved"][:100]
        self._flush()
        return entry["id"]

    def delete_saved(self, saved_id: str):
        self._data["saved"] = [s for s in self._data["saved"] if s["id"] != saved_id]
        self._flush()

    def get_saved(self) -> list:
        return self._data["saved"]

    # ── Favorites ─────────────────────────────────────────────────────────────

    def add_favorite(self, session_id: str):
        if session_id not in self._data["favorites"]:
            self._data["favorites"].insert(0, session_id)
            self._flush()

    def remove_favorite(self, session_id: str):
        self._data["favorites"] = [
            f for f in self._data["favorites"] if f != session_id
        ]
        self._flush()

    def is_favorite(self, session_id: str) -> bool:
        return session_id in self._data["favorites"]

    def get_favorites(self) -> list:
        fav_ids = set(self._data["favorites"])
        return [s for s in self._data["sessions"] if s["id"] in fav_ids]
