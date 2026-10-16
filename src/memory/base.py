"""Memory chooses which past messages of a conversation the decision model sees.

It never stores anything: the Session always keeps the full conversation (and a
checkpointer, later, saves the Session). Memory only selects from it, each time a
decision's state text is built.
"""


class Memory:
    """Base class. `enabled` is False only for NoMemory (the model sees no past messages)."""

    enabled = True

    def messages(self, history, limit=None):
        """Past messages to show the model, oldest first, as [(role, text)].

        history  the Session's full conversation; its last item is the current user message,
                 which is never included here (the steps always add it themselves)
        limit    the most past messages a step wants, or None for no step cap. Only step
                 2a2 sets one (4), so it sees min(k, 4) messages; every other step
                 sees what the memory gives (k messages, or all with k=None)
        """
        raise NotImplementedError


class NoMemory(Memory):
    """The model sees only the current message. The default when no memory is given.

    Without memory: picking from a list the agent showed ("the first one"), bare replies
    to a list question ("B5678" after "which order?") and short follow-ups ("cancel it")
    lose their context. Answers to a paused question still work (step 0 keeps the question).
    """

    enabled = False

    def messages(self, history, limit=None):
        return []
