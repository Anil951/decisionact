"""SqliteCheckpointer: conversations in a local SQLite file (Python's built-in sqlite3)."""
import json
import re
import sqlite3
import threading
from datetime import datetime, timezone

from .base import Checkpointer


def _table_name(table):
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table):
        raise ValueError(f"invalid table name: {table!r}")
    return table


class SqliteCheckpointer(Checkpointer):
    """SqliteCheckpointer("chat.db")   one row per conversation: session_id, JSON data,
    updated_at"""

    def __init__(self, path, table="decisionact_sessions", timeout=10.0):
        self.path, self.table = path, _table_name(table)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(path, timeout=timeout, check_same_thread=False)
        with self._lock, self._db:
            self._db.execute(f"CREATE TABLE IF NOT EXISTS {self.table} ("
                             "session_id TEXT PRIMARY KEY, data TEXT NOT NULL, "
                             "updated_at TEXT NOT NULL)")

    def __repr__(self):
        return f"SqliteCheckpointer({self.path!r})"

    def load(self, session_id):
        with self._lock:
            row = self._db.execute(f"SELECT data FROM {self.table} WHERE session_id = ?",
                                   (session_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def save(self, session_id, data):
        with self._lock, self._db:
            self._db.execute(
                f"INSERT INTO {self.table} (session_id, data, updated_at) VALUES (?, ?, ?) "
                f"ON CONFLICT(session_id) DO UPDATE SET data = excluded.data, "
                f"updated_at = excluded.updated_at",
                (session_id, json.dumps(data), datetime.now(timezone.utc).isoformat()))

    def delete(self, session_id):
        with self._lock, self._db:
            self._db.execute(f"DELETE FROM {self.table} WHERE session_id = ?", (session_id,))

    def list(self):
        with self._lock:
            return [r[0] for r in self._db.execute(f"SELECT session_id FROM {self.table}")]

    def close(self):
        self._db.close()
