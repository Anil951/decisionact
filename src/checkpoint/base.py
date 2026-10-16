"""A checkpointer saves each conversation (the agent's Session) so it survives restarts and
can be continued by any process. Memory is different: it only chooses which past messages
the decision model sees; the checkpointer stores the whole Session.

Only the latest state of each conversation is kept: every save replaces the previous one.
"""


class Checkpointer:
    """Interface for every storage. A custom one (Redis, files, S3, ...) implements these.
    The saved data is a JSON-ready dict (Session.to_dict())."""

    def load(self, session_id):
        """The saved data, or None if the conversation was never saved."""
        raise NotImplementedError

    def save(self, session_id, data):
        """Store `data` for the conversation, replacing what was saved before."""
        raise NotImplementedError

    def delete(self, session_id):
        """Forget the conversation (no error if it does not exist)."""
        raise NotImplementedError

    def list(self):
        """All saved session ids."""
        raise NotImplementedError
