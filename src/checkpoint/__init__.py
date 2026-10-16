"""SQLite conversation storage.

SqliteCheckpointer("chat.db") persists sessions across restarts.
SqliteCheckpointer(":memory:") keeps sessions for this process only (Agent default).
Subclass Checkpointer to integrate custom storage.
"""
from .base import Checkpointer
from .sqlite import SqliteCheckpointer

__all__ = ["Checkpointer", "SqliteCheckpointer"]
