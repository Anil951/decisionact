"""Conversation memory: which past messages the decision model sees. Pass one to
Agent(..., memory=...); without it the agent uses NoMemory (current message only).

  NoMemory()                      only the current message (default)
  ConversationBufferMemory(k=7)   the last k messages; k=None for the whole conversation

Every decision sees the memory's messages, except step 2a2 (is an optional input
given?), which sees at most 4: min(k, 4), or 4 with k=None.
"""
from .base import Memory, NoMemory
from .conversation_buffer_memory import ConversationBufferMemory

__all__ = ["Memory", "NoMemory", "ConversationBufferMemory"]
