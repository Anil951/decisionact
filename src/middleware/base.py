"""Middleware: objects that hook into the steps of a turn. Pass a list to
Agent(..., middleware=[...]); each is called in the order given.

Today there are two hooks, before_tool and answer_interrupt. More hooks (around a turn,
around each decision, after a tool) can be added here later without changing the middleware
written so far.
"""


class Interrupt(Exception):
    """Raised by a middleware hook to stop the turn and wait for something outside the agent
    (for example a person). `reply` is what the user is told meanwhile."""

    def __init__(self, reply):
        super().__init__(reply)
        self.reply = reply


class Middleware:
    """Base class. Override the hooks you need."""

    def validate(self, agent):
        """Called once when the Agent is built. Raise ValueError for a setup that cannot
        work (for example a rule that names a tool the agent does not have)."""

    def before_tool(self, agent, sess, intent, tool, args, calls):
        """Called after a tool's inputs are resolved and before the tool runs.
        agent, sess  the Agent and the conversation's Session
        intent       the intent being handled
        tool, args   the Tool and its resolved inputs
        calls        the tool calls already made this turn: [(name, inputs, output)]
        Return normally to let the tool run; raise Interrupt to stop the turn instead
        (the tool does not run)."""

    def answer_interrupt(self, sess, message):
        """Called with each new user message while a turn is interrupted (a tool call waits
        for approval). Return a decision (see humanintheloop.Decision) if the message
        answers the interruption; return None otherwise, and the user just gets the waiting
        reply again."""
        return None
