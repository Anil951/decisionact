"""SQLite conversation storage.

SqliteCheckpointer("chat.db") persists sessions across restarts.
SqliteCheckpointer(":memory:") explicitly enables temporary SQLite storage.
Agents default to checkpointing disabled and retain sessions in plain Python memory.
Subclass Checkpointer to integrate custom storage.
"""
from .base import Checkpointer
from .sqlite import SqliteCheckpointer

__all__ = ["Checkpointer", "SqliteCheckpointer"]
