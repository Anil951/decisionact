"""DecisionAct main module: what an agent is built from, and the Agent that runs it.

An agent file declares

  tools    plain functions marked with @tool (docstring = description, Param per input)
  INTENTS  {name: Intent(desc, context, tools=[tool names], outcomes=[outcome names])}
           (tools may be empty, e.g. a greeting: it goes straight to its outcome)
  OUTCOMES {name: Outcome(desc, reply)}

and builds  Agent(tools=[...], intents=INTENTS, outcomes=OUTCOMES, model=<decision model>).
The Agent validates the spec at startup. For each message it loads the conversation's
Session from its checkpointer, runs the steps in steps.py, fills the chosen outcome's
reply, and saves the Session again. Each message handles one intent.

This module defines:
  limits     default safety caps (below); MESSAGES  the agent's own fallback wording
  Param, Tool, @tool      tools and their inputs
  Intent, Outcome         the agent spec
  TurnResult              what agent.turn() returns: reply, intent, outcome, tool calls,
                          decisions, paused call
  Session                 everything recorded for one conversation (the full history is
                          always kept; the agent's memory only chooses what the model sees);
                          to_dict() / from_dict() for checkpointers
  reply helpers           filling reply templates from tool inputs/outputs
  Agent                   turn(message, session_id), resume(session_id, decision),
                          pending_approval(), history(), reset(), startup
                          validation; built with a decision model (decisionact.models) and,
                          optionally, a memory (decisionact.memory), a checkpointer
                          (decisionact.checkpoint) and middleware (decisionact.middleware)

Limits: safety caps with defaults; each agent can override any of them, the rest keep
their defaults:

  Agent(tools=[...], intents=INTENTS, outcomes=OUTCOMES, max_calls=10, max_asks=3)

  max_calls        (6)   tool calls per turn; stops endless tool loops. When reached, the
                         loop ends and the outcome is decided from the results so far.
  max_param_tries  (3)   values a tool may reject for one input (e.g. "order not found")
                         before the agent stops guessing and asks the user to type it.
  max_candidates   (40)  options in the sliding-window Choice; keeps the decision request small.
  window           (3)   longest sliding-window candidate, in words: every 1..window-word
                         span of the message is a candidate when the regex finds nothing.
  max_asks         (2)   times a paused call may ask for the same missing input; after
                         that the call is dropped and the "stopped" message is sent.

  Every value must be a positive integer; anything else raises an error at startup.
"""
import copy
import inspect
from dataclasses import dataclass, field
from typing import Callable

from .checkpoint import Checkpointer, SqliteCheckpointer
from .memory import Memory, NoMemory
from .middleware import Interrupt, Middleware, PendingApproval
from .models import DecisionModel, LowConfidence, decision_log

# Default limits; an agent can override any of them: Agent(..., max_calls=10, max_asks=3)
MAX_CALLS = 6          # tool calls per turn
MAX_PARAM_TRIES = 3    # values a tool may reject before asking the user to type the value
MAX_CANDIDATES = 40    # options in the sliding-window Choice
WINDOW = 3             # sliding window: candidates are every 1..WINDOW-word span
MAX_ASKS = 2           # times a paused call may ask for the same missing input

MESSAGES = {  # the agent's own wording, filled from the input's description
    "rephrase": "Sorry, I didn't quite get that. Could you rephrase?",
    "ask_value": "I need the {name} ({desc}). Please type it.",
    "ask_option": "Please tell me the {name}: {options}.",
    "stopped": "Sorry, I couldn't complete that. Please try again.",

}


# ======================= TOOLS =======================
@dataclass
class Param:
    """One tool input.
    Non-categorical: `pattern` (regex for the value's exact format) is tried first; if it
      finds nothing, every 1..window-word span of the message is a candidate for a Choice.
    Categorical: `options` {category: meaning}; the decision model classifies the message into one.
    Optional: a Noul first decides if the current message gives this input at all; if not,
      the tool is called without it (the function's default is used).
    Values are passed to the tool exactly as the user wrote them (no normalisation)."""
    desc: str
    pattern: str | None = None
    options: dict | None = None
    optional: bool = False


@dataclass
class Tool:
    name: str
    fn: Callable
    desc: str
    params: dict

    def run(self, **args):
        try:
            return self.fn(**args)
        except Exception as e:     # tools stay plain: failures become output JSON
            return {"error": str(e)}


def tool(fn=None, **params):
    """Mark a plain function as a tool. Docstring = description, signature = inputs,
    keyword arguments = a Param for each input:

        @tool(order_id=Param(desc="the order ID", pattern=r"[A-Z]\\d{4}"))
        def get_order(order_id: str) -> dict:
            "Look up an order."
    """
    def mark(f):
        signature = inspect.signature(f).parameters
        inputs = list(signature)
        if set(params) != set(inputs):
            raise TypeError(f"{f.__name__}: give a Param for exactly these inputs: {inputs}")
        for n, p in params.items():
            if not p.desc:
                raise TypeError(f"{f.__name__}.{n}: Param needs a desc")
            if p.pattern and p.options:
                raise TypeError(f"{f.__name__}.{n}: use pattern or options, not both")
            if p.optional and signature[n].default is inspect.Parameter.empty:
                raise TypeError(f"{f.__name__}.{n}: an optional input needs a default value")
        if not inspect.getdoc(f):
            raise TypeError(f"{f.__name__}: the docstring is the tool description")
        f.tool = Tool(f.__name__, f, inspect.getdoc(f), dict(params))
        return f                   # the function itself is unchanged
    return mark(fn) if fn else mark


# ======================= INTENTS / OUTCOMES =======================
@dataclass
class Intent:
    """One kind of user request. Every intent has the same shape.
    desc      what the intent means; the decision model uses it to classify the user's message
    context   how to handle it; added to every decision after classification
              (tool choice, inputs, after-tool checks, outcome)
    tools     names of the tools this intent may call (empty: no tool loop)
    outcomes  names of the outcomes this intent may end with (at least one)"""
    desc: str
    context: str = ""
    tools: list = field(default_factory=list)
    outcomes: list = field(default_factory=list)


@dataclass
class Outcome:
    """One way a turn can end.
    desc   what happened; the decision model uses it to choose the outcome
    reply  the predefined reply; {placeholders} are filled from the tool inputs/outputs"""
    desc: str
    reply: str


# ======================= SESSION =======================
class _Ask(Exception):
    """Stop the turn and ask the user for an input (kind "asking"), or give up on the paused
    call (kind "stopped")."""
    def __init__(self, text, kind="asking"):
        self.text, self.kind = text, kind


@dataclass
class TurnResult:
    """Everything that happened in one turn; agent.turn() returns it.
    print(result) shows all of it (it is a dataclass); the text for the user is
    result.reply.

    reply       the text for the user
    intent      the intent chosen (None if the turn stopped before choosing one)
    outcome     the outcome whose reply was sent, or "rephrase" (a decision was too unsure),
                "asking" (a tool input is missing, the reply is the question) or "stopped"
                (the same question was asked max_asks times) or "awaiting_approval" (a person must
                approve a tool call first, see decisionact.middleware)
    tool_calls  [{"tool", "inputs", "output"}] in the order they ran
    decisions   [{"step", "type", "answer", "confidence", ...}] in the order they were made;
                for a noul "answer" is the probability of yes; a choice also has
                "low_confidence"
    paused      the tool call waiting for the user's next message, or None
    pending_approval  the tool call waiting for a person's approval, or None. A
                PendingApproval: .intent, .tool, .inputs and .actions (the approve / reject
                commands to show; send one to agent.turn(command, session_id))
    """
    reply: str
    intent: str | None = None
    outcome: str | None = None
    tool_calls: list = field(default_factory=list)
    decisions: list = field(default_factory=list)
    paused: dict | None = None
    pending_approval: PendingApproval | None = None


class Session:
    def __init__(self):
        self.history = []        # [(role, text)]; the current user message is last
        self.slots = {}          # inputs resolved for the current request
        self.rejected = {}       # input -> values a tool rejected
        self.attempts = {}       # input -> rejected-value count
        self.exact_wait = set()  # inputs we asked the user to type exactly
        self.exact = set()       # inputs the user typed after we asked (trusted)
        self.paused = None       # tool call stopped for a missing input:
                                 #   {intent, tool, input, question, asks}
        self.resumed = None      # the paused call being continued in this turn
        self.pending_approval = None  # tool call waiting for a person's approval:
                                 #   {intent, tool, inputs, calls, waiting_reply, rejected_outcome}
        self.last = {}           # input -> last value that worked ("cancel it")

    # ---------- saving (checkpointers) ----------
    VERSION = 1  # format of to_dict(); bump when it changes

    def to_dict(self):
        """Everything needed to continue the conversation, as JSON-ready data.
        `resumed` is not saved: it only lives during one turn."""
        return {"v": self.VERSION,
                "history": [list(m) for m in self.history],
                "slots": dict(self.slots),
                "rejected": {k: list(v) for k, v in self.rejected.items()},
                "attempts": dict(self.attempts),
                "exact_wait": sorted(self.exact_wait),
                "exact": sorted(self.exact),
                "paused": self.paused,
                "pending_approval": self.pending_approval,
                "last": dict(self.last)}

    @classmethod
    def from_dict(cls, data):
        if data.get("v") != cls.VERSION:
            raise ValueError(f"saved session has format v{data.get('v')}, "
                             f"this version reads v{cls.VERSION}")
        sess = cls()
        sess.history = [tuple(m) for m in data["history"]]
        sess.slots = dict(data["slots"])
        sess.rejected = {k: set(v) for k, v in data["rejected"].items()}
        sess.attempts = dict(data["attempts"])
        sess.exact_wait, sess.exact = set(data["exact_wait"]), set(data["exact"])
        sess.paused, sess.last = data["paused"], dict(data["last"])
        sess.pending_approval = data.get("pending_approval")
        return sess


class _Blank(dict):
    def __missing__(self, key):
        return ""


def _render(template, values):
    return template.format_map(_Blank(values))


def _show(item):
    """One list item for a reply: a dict shows as 'first value (other values)'."""
    if isinstance(item, dict):
        values = [str(v) for v in item.values()]
        return values[0] + (f" ({', '.join(values[1:])})" if len(values) > 1 else "")
    return str(item)


def _facts(calls):
    """Tool inputs/outputs of this turn for reply templates; lists become one line per item."""
    out = {}
    for _, args, result in calls:
        out.update(args)
        if isinstance(result, dict):
            out.update(result)
    return {k: "\n".join(f"- {_show(i)}" for i in v) if isinstance(v, list) else v
            for k, v in out.items()}


# The steps of a turn (steps.py) use the definitions above, so they are imported here.
from . import steps  # noqa: E402


# ======================= AGENT =======================
class Agent:
    """An agent built from a spec: tools (@tool functions), intents (Intent) and
    outcomes (Outcome), answered by a decision model (models package).
    Use agent.turn(message, session_id): one message in, a TurnResult out (the user's text
    is result.reply). If a tool call needs a person's approval (HumanInTheLoopMiddleware),
    the user answers with /approve or /reject [reason] in agent.turn(); agent.resume(
    session_id, approve() or reject(reason)) does the same from your own code.

    model: a DecisionModel, e.g. SystemOneModel(api_key) or CloudflareModel(api_token, account_id).
    memory: which past messages the model sees, e.g. ConversationBufferMemory(k=7) (last 7)
            or ConversationBufferMemory() (all). Every decision sees them, except step 2a2,
            which sees at most 4: min(k, 4).
            None (default) = NoMemory: the model sees only the current message, so picking
            from a list ("the first one") and bare replies to a list question lose context.
    checkpointer: where conversations are saved, e.g. SqliteCheckpointer("chat.db").
            None (default) = SqliteCheckpointer(":memory:"): conversations are lost on restart.
            Each turn loads the conversation (by session_id), runs, and saves it.
    middleware: a list of Middleware (decisionact.middleware), called in order, e.g.
            [HumanInTheLoopMiddleware(approvals={...})]. None (default) = no middleware.
    Optional limits (keyword only, defaults in brackets):
      max_calls=6        tool calls per turn
      max_param_tries=3  values a tool may reject for one input before asking the user
      max_candidates=40  options in the sliding-window Choice
      window=3           longest sliding-window candidate, in words
      max_asks=2         asks for the same missing input before the paused call is dropped
    """

    def __init__(self, tools, intents, outcomes, model, *, max_calls=MAX_CALLS,
                 max_param_tries=MAX_PARAM_TRIES, max_candidates=MAX_CANDIDATES,
                 window=WINDOW, max_asks=MAX_ASKS, memory=None, checkpointer=None, middleware=None):
        if not isinstance(model, DecisionModel):
            raise TypeError("model must be a DecisionModel, e.g. SystemOneModel(api_key)")
        if memory is not None and not isinstance(memory, Memory):
            raise TypeError("memory must be a Memory, e.g. ConversationBufferMemory(k=7)")
        if checkpointer is not None and not isinstance(checkpointer, Checkpointer):
            raise TypeError("checkpointer must be a Checkpointer, e.g. SqliteCheckpointer('chat.db')")
        middleware = list(middleware or [])
        for mw in middleware:
            if not isinstance(mw, Middleware):
                raise TypeError(f"middleware must be Middleware objects, got {mw!r}")
        self.model = model
        self.middleware = middleware
        self.memory = memory or NoMemory()
        self.checkpointer = checkpointer if checkpointer is not None else SqliteCheckpointer(":memory:")
        limits = {"max_calls": max_calls, "max_param_tries": max_param_tries,
                  "max_candidates": max_candidates, "window": window, "max_asks": max_asks}
        for name, value in limits.items():
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(f"{name} must be a positive integer, got {value!r}")
        self.max_calls, self.max_param_tries = max_calls, max_param_tries
        self.max_candidates, self.window, self.max_asks = max_candidates, window, max_asks
        self.tools = {}
        for f in tools:
            t = getattr(f, "tool", None)
            if t is None:
                raise TypeError(f"{getattr(f, '__name__', f)} is not marked with @tool")
            self.tools[t.name] = t
        self.intents, self.outcomes = intents, outcomes
        for name, o in outcomes.items():  # validate the spec once
            if not isinstance(o, Outcome):
                raise TypeError(f"outcome {name}: must be an Outcome(desc, reply)")
        for name, spec in intents.items():
            if not isinstance(spec, Intent):
                raise TypeError(f"intent {name}: must be an Intent(...)")
            if not spec.outcomes:
                raise ValueError(f"intent {name}: needs at least one outcome")
            for t in spec.tools:
                if t not in self.tools:
                    raise ValueError(f"intent {name}: unknown tool {t}")
            for o in spec.outcomes:
                if o not in outcomes:
                    raise ValueError(f"intent {name}: outcome '{o}' is not defined in OUTCOMES")
        for mw in self.middleware:  # needs the spec above
            mw.validate(self)

    # ---------- public ----------
    def turn(self, message, session_id="default"):
        """One user message in, a TurnResult out, for the conversation `session_id` (your
        app picks it: a user id, chat id, ...). The conversation is loaded from the
        checkpointer before the turn and saved after it. Like invoke() in other agent
        frameworks. The result holds the reply, the intent, the outcome, every tool call and
        every decision made (see TurnResult). While a tool call waits for a person's
        approval, the middleware reads the message: an approval command (/approve,
        /reject [reason]) answers it, anything else only gets the waiting reply."""
        sess = self._load(session_id)
        sess.history.append(("user", message))
        if sess.pending_approval:
            for mw in self.middleware:
                decision = mw.answer_interrupt(sess, message)
                if decision is not None:
                    return self._execute(session_id, sess,
                                         lambda s, r: self._decide_approval(s, r, decision))
            return self._execute(session_id, sess, self._waiting)
        return self._execute(session_id, sess, self._handle)

    def resume(self, session_id, decision):
        """A person's answer to the tool call waiting for approval: approve() runs it and the
        turn carries on, reject(reason) ends the turn with the rule's rejected outcome.
        Returns a TurnResult like turn()."""
        sess = self._load(session_id)
        if not sess.pending_approval:
            raise ValueError(f"session {session_id!r}: nothing is waiting for approval")
        return self._execute(session_id, sess, lambda s, r: self._decide_approval(s, r, decision))

    def pending_approval(self, session_id="default"):
        """The tool call waiting for approval in this conversation (a PendingApproval), or
        None."""
        return PendingApproval.from_saved(self._load(session_id).pending_approval)

    def _execute(self, session_id, sess, run):
        """Run `run(sess, result)` -> reply with the bookkeeping every kind of turn needs:
        record decisions, turn stops into fallback replies, save the conversation."""
        result = TurnResult(reply="")
        token = decision_log.set(result.decisions)   # models record each decision here
        try:
            try:
                result.reply = run(sess, result)
            except LowConfidence:
                result.reply, result.outcome = MESSAGES["rephrase"], "rephrase"
            except _Ask as a:
                result.reply, result.outcome = a.text, a.kind
            except Interrupt as i:                  # a middleware stopped the turn
                result.reply, result.outcome = i.reply, "awaiting_approval"
        finally:
            decision_log.reset(token)
        result.paused = copy.deepcopy(sess.paused)
        result.pending_approval = PendingApproval.from_saved(sess.pending_approval)
        sess.history.append(("agent", result.reply))
        self.checkpointer.save(session_id, sess.to_dict())
        return result

    def history(self, session_id="default"):
        """The saved conversation: [(role, text)]."""
        return self._load(session_id).history

    def reset(self, session_id="default"):
        """Forget the conversation (deletes it from the checkpointer)."""
        self.checkpointer.delete(session_id)

    def _load(self, session_id):
        """The Session from the checkpointer; a new Session if never saved. A saved paused
        call whose tool or intent no longer exists (the agent changed) is dropped."""
        data = self.checkpointer.load(session_id)
        if data is None:
            return Session()
        sess = Session.from_dict(data)
        p = sess.paused
        if p and (p["intent"] not in self.intents or p["tool"] not in self.tools
                  or p["input"] not in self.tools[p["tool"]].params):
            sess.paused = None
            sess.slots.clear()
        return sess

    # ---------- turn ----------
    def _waiting(self, sess, result):
        """The user wrote while a tool call waits for approval: nothing runs."""
        result.intent = sess.pending_approval["intent"]
        result.outcome = "awaiting_approval"
        return sess.pending_approval["waiting_reply"]

    def _decide_approval(self, sess, result, decision):
        """Carry out a person's decision on the pending tool call."""
        pending, sess.pending_approval = sess.pending_approval, None
        result.intent = pending["intent"]
        spec = self.intents[pending["intent"]]
        calls = [tuple(c) for c in pending["calls"]]
        if not decision.approved:                    # the tool never runs
            outcome = pending["rejected_outcome"]
            result.outcome = outcome
            facts = {**_facts(calls), **pending["inputs"], "rejection_reason": decision.reason}
            sess.slots.clear()
            return _render(self.outcomes[outcome].reply, facts)
        sess.slots = dict(pending["inputs"])         # all inputs are known: no asking again
        outcomes = {o: self.outcomes[o] for o in spec.outcomes}
        calls, outcome = steps.tool_loop(self, sess, pending["intent"], spec, outcomes,
                                         pending["tool"], result.tool_calls, calls, approved=True)
        return self._finish(sess, result, spec, outcomes, calls, outcome)

    def _handle(self, sess, result):
        """Run the steps of one turn (see steps.py); fills result.intent / outcome /
        tool_calls as it goes, so they are known even if the turn stops early."""
        # ---- 0. continue a paused call? ----
        paused, sess.paused, sess.resumed = sess.paused, None, None
        if paused and steps.decide_continue(self, sess, paused):
            sess.resumed = paused              # skip 1 and 2a
            intent = paused["intent"]
        else:
            sess.slots.clear()                 # a new request: drop half-filled inputs
            intent = steps.decide_intent(self, sess)                        # ---- 1. intent ----
        result.intent = intent
        spec = self.intents[intent]
        outcomes = {o: self.outcomes[o] for o in spec.outcomes}
        resume_tool = sess.resumed["tool"] if sess.resumed else None
        # ---- 2. intermediate decisions (tool loop) ----
        calls, outcome = (steps.tool_loop(self, sess, intent, spec, outcomes, resume_tool,
                                          result.tool_calls)
                          if spec.tools else ([], None))  # no tools: straight to the outcome
        return self._finish(sess, result, spec, outcomes, calls, outcome)

    def _finish(self, sess, result, spec, outcomes, calls, outcome):
        """---- 3. outcome: decide it if the tool loop did not, then fill its reply."""
        if outcome is None and len(outcomes) == 1:   # only one way to end: nothing to decide
            outcome = next(iter(outcomes))
        if outcome is None:
            outcome = steps.decide_outcome(self, sess, outcomes, spec.context, calls)
        result.outcome = outcome
        sess.slots.clear()
        return _render(self.outcomes[outcome].reply, _facts(calls))
