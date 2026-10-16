"""ConversationBufferMemory: the model sees the recent conversation."""
from .base import Memory


class ConversationBufferMemory(Memory):
    """The last `k` past messages (user and agent), or all of them when k is None.

        ConversationBufferMemory(k=7)    last 7 messages (the usual setting)
        ConversationBufferMemory()       the whole conversation

    Every decision sees these messages, except step 2a2 (is an optional input given?),
    which sees at most 4: min(k, 4), or 4 with k=None.

    A message is one user message or one agent reply. Prefer a k: the whole conversation
    grows the state of every decision, making requests slower and costlier, and a long
    chat can exceed the decision model's input limit.
    """

    def __init__(self, k=None):
        if k is not None and (not isinstance(k, int) or isinstance(k, bool) or k < 1):
            raise ValueError(f"ConversationBufferMemory: k must be a positive integer or None, "
                             f"got {k!r}")
        self.k = k

    def __repr__(self):
        return f"ConversationBufferMemory(k={self.k!r})"

    def messages(self, history, limit=None):
        past = history[:-1]                    # the current message is added by the steps
        caps = [n for n in (self.k, limit) if n is not None]
        return list(past[-min(caps):]) if caps else list(past)
