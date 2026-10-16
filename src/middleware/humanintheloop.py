"""Human in the loop: a person approves or rejects chosen tool calls before they run.

    from decisionact.middleware import Approval, HumanInTheLoopMiddleware, approve, reject

    Agent(..., checkpointer=SqliteCheckpointer("chat.db"),
          middleware=[HumanInTheLoopMiddleware(approvals={
              "cancel_order": Approval(rejected_outcome="cancel_rejected",
                                       waiting="Cancelling order {order_id} needs approval.")})])

How it works
  1. The user's request is handled as usual until the tool's inputs are resolved.
  2. For a tool with an Approval rule the tool does NOT run. turn() ends with
     result.outcome == "awaiting_approval", result.reply = the rule's `waiting` text (as the
     agent wrote it) and result.pending_approval = a PendingApproval: .intent, .tool,
     .inputs and .actions, the two things a person can do with their commands. The pending
     call is saved with the conversation by the checkpointer, so the wait can be long and
     another process can end it.
  3. While it waits, the framework itself reads the next message in turn():
       /approve            runs the tool with the saved inputs; the turn carries on as normal
       /reject [reason]    the tool never runs; the turn ends with the rule's rejected_outcome,
                           an Outcome defined in OUTCOMES whose reply may use
                           {rejection_reason} next to the tool's inputs and earlier outputs
       anything else       only gets the waiting reply again; nothing runs
     So the agent's own code has no approval handling: it just calls agent.turn(...).
     agent.resume(session_id, approve() / reject(reason)) does the same programmatically,
     for a reviewer who answers from another system.

No decision model is involved: the commands are matched exactly (see parse_command).
The rejected outcome is chosen by the rule, so it is not listed in any Intent's outcomes.
Note: the commands arrive through turn(), so whoever chats can answer them; to let only a
separate reviewer decide, show the approval to them and call agent.resume() yourself.
"""
import copy
from dataclasses import dataclass

from .base import Interrupt, Middleware


@dataclass
class Decision:
    """A person's answer to a pending approval. Create it with approve() or reject()."""
    approved: bool
    reason: str = ""


def approve():
    """Let the waiting tool call run."""
    return Decision(True)


def reject(reason="no reason given"):
    """Do not run the waiting tool call; the turn ends with the rule's rejected outcome."""
    return Decision(False, reason)


APPROVE_COMMAND = "/approve"
REJECT_COMMAND = "/reject"


@dataclass
class PendingApproval:
    """The tool call waiting for a person's approval (result.pending_approval).
    intent, tool, inputs  what is waiting
    actions               what a person can do and the command that does it, for a UI to
                          show: [{"action": "approve", "command": "/approve"},
                                 {"action": "reject", "command": "/reject"}]
                          (send a command to agent.turn(command, session_id))"""
    intent: str
    tool: str
    inputs: dict
    actions: list

    @classmethod
    def from_saved(cls, saved):
        """Build it from the pending call saved in the Session (None stays None). The
        actions are not saved: they always come from the command constants."""
        if not saved:
            return None
        return cls(intent=saved["intent"], tool=saved["tool"], inputs=copy.deepcopy(saved["inputs"]),
                   actions=[{"action": "approve", "command": APPROVE_COMMAND},
                            {"action": "reject", "command": REJECT_COMMAND}])


def parse_command(message):
    """Match a user message against the approval commands, exactly (no model):
    "/approve" -> approve(); "/reject" or "/reject <reason>" -> reject(reason);
    anything else -> None. Commands are not case sensitive; a reason keeps its case."""
    text = message.strip()
    head, _, rest = text.partition(" ")
    if text.lower() == APPROVE_COMMAND:
        return approve()
    if head.lower() == REJECT_COMMAND:
        return reject(rest.strip() or "no reason given")
    return None


@dataclass
class Approval:
    """The rule for one tool.
    rejected_outcome  name of the Outcome used when the call is rejected (must exist in
                      OUTCOMES); its reply can use the tool's inputs, earlier tool outputs of
                      the turn and {rejection_reason}
    waiting           what the user is told while the call waits; {placeholders} are filled
                      from the tool's inputs and earlier tool outputs of the turn.
                      How to approve or reject is not part of it: a UI shows
                      result.pending_approval.actions"""
    rejected_outcome: str
    waiting: str = "This needs a person's approval first. I'll continue once it is approved."


class HumanInTheLoopMiddleware(Middleware):
    """HumanInTheLoopMiddleware(approvals={tool name: Approval(...)}) - approve/reject
    before the listed tools run."""

    def __init__(self, approvals):
        if not approvals:
            raise ValueError("HumanInTheLoopMiddleware: give at least one tool to approve")
        for tool, rule in approvals.items():
            if not isinstance(rule, Approval):
                raise TypeError(f"approvals[{tool!r}] must be an Approval(...)")
        self.approvals = dict(approvals)

    def validate(self, agent):
        for tool, rule in self.approvals.items():
            if tool not in agent.tools:
                raise ValueError(f"HumanInTheLoopMiddleware: unknown tool {tool!r}")
            if rule.rejected_outcome not in agent.outcomes:
                raise ValueError(f"HumanInTheLoopMiddleware: outcome {rule.rejected_outcome!r} "
                                 f"(rejected_outcome of {tool!r}) is not defined in OUTCOMES")

    def before_tool(self, agent, sess, intent, tool, args, calls):
        rule = self.approvals.get(tool.name)
        if rule is None:
            return
        from ..main import _facts, _render  # imported late: main imports this package
        waiting = _render(rule.waiting, {**_facts(calls), **args})
        sess.pending_approval = {"intent": intent, "tool": tool.name, "inputs": dict(args),
                                 "calls": copy.deepcopy([list(c) for c in calls]),
                                 "waiting_reply": waiting,
                                 "rejected_outcome": rule.rejected_outcome}
        raise Interrupt(waiting)

    def answer_interrupt(self, sess, message):
        pending = sess.pending_approval
        if pending and pending["tool"] in self.approvals:
            return parse_command(message)
        return None
