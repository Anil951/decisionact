"""The steps of one turn. main.Agent runs them in this order for every message:

  0. continue a paused call?  [DECISION] Noul, only when the last turn stopped to ask for a
                              missing tool input. Yes (the message answers the question): skip
                              1 and 2a, resolve the missing input, run the paused tool, continue
                              from 2c. No (a new or different request, e.g. "hi"): drop the
                              paused call and its resolved inputs, start at 1. A paused input is
                              asked for at most max_asks times; after that the call is dropped.
                              -> decide_continue, pause
  1. intent                   [DECISION] Choice over the intents                -> decide_intent
  2. intermediate decisions   tool_loop repeats a -> b -> tool -> c:
       a. tool                [DECISION] Choice over the intent's tools + none  -> decide_tool
       a2. optional input?    [DECISION] Noul per optional input: does this message give or
                              pick it?                                    -> decide_input_needed
       b. inputs              categories -> [DECISION] Choice; otherwise regex on the message,
                              then (for a picked optional input) regex on the agent's last
                              message, then sliding window -> [DECISION] Choice; a value the
                              tool rejects is replaced, max_param_tries times
                              -> resolve_params, resolve_param, decide_span, decide_option,
                                 wrong_input
       c. after the tool      [DECISION] Nouls "another tool?" + "wrong input?" + Choice
                              outcome, in one request                     -> decide_after_tool
  3. outcome                  [DECISION] Choice over the intent's outcomes, when the loop did
                              not already decide it                       -> decide_outcome

Every function takes the `agent` first: it carries the decision model (agent.model), the
spec (agent.tools, agent.intents, agent.outcomes) and the limits (agent.max_calls, ...).
Functions marked [DECISION] ask the decision model; the rest is plain code.
"""
import copy
import re

from .main import MESSAGES, _Ask, _render
from .models import LowConfidence

_WORD = re.compile(r"\w(?:[\w\-./@#:]*\w)?")  # word tokens; edge punctuation like "?" is dropped


# ======================= STATE TEXT =======================
def _past(agent, sess, title, limit):
    """Past messages chosen by the agent's memory, under a title (nothing without memory)."""
    if not agent.memory.enabled:
        return []
    return [title] + [f"{r}: {t}" for r, t in agent.memory.messages(sess.history, limit)]


def build_state(agent, sess, context="", calls=()):
    """Main state for every decision call: past messages (as many as the memory's k allows,
    all with k=None), current message, context, tool calls."""
    lines = _past(agent, sess, "Conversation so far:", None)
    lines.append(f"Current user message: {sess.history[-1][1]}")
    if context:
        lines.append(f"Context: {context}")
    if calls:
        lines.append("Tool calls this turn (tool, input, output):")
        lines += [f"- {n}({a}) -> {r}" for n, a, r in calls]
    return "\n".join(lines)


def param_state(agent, sess, tool, pname, context):
    return (build_state(agent, sess, context)
            + f"\nTool: {tool.desc}\nInput {pname}: {tool.params[pname].desc}")


# ======================= 0. CONTINUE A PAUSED CALL =======================
def decide_continue(agent, sess, paused):
    """[DECISION] Noul: is the current message an answer to the agent's question for the
    missing input (continue the paused call), rather than a new or different request?"""
    tool = agent.tools[paused["tool"]]
    param = tool.params[paused["input"]]
    lines = [f"The agent asked the user: {paused['question']}",
             f"Current user message: {sess.history[-1][1]}",
             f"Paused request: {paused['intent']} - {agent.intents[paused['intent']].desc}",
             f"Paused tool: {tool.desc}",
             f"Missing input {paused['input']}: {param.desc}"]
    if param.options:
        lines.append("Possible values: " + ", ".join(param.options))
    if sess.slots:
        lines.append(f"Already given: {sess.slots}")
    p = agent.model.noul("\n".join(lines),
                         f"Is the user's current message an answer to the agent's question (giving "
                         f"the missing {paused['input']}, even vaguely), rather than a new or "
                         f"different request such as a greeting or another question?",
                         label=f"0. continue paused {paused['tool']}?")
    return p >= 0.5


def pause(agent, sess, intent, tool, pname, question):
    """Remember the tool call that stopped for a missing input, so the next message can
    continue it (step 0). After max_asks asks for the same input the call is dropped."""
    prev = sess.resumed
    asks = (prev["asks"] + 1 if prev and prev["tool"] == tool.name and prev["input"] == pname
            else 1)
    if asks > agent.max_asks:
        sess.slots.clear()
        sess.exact_wait.discard(pname)
        raise _Ask(MESSAGES["stopped"], "stopped")
    sess.paused = {"intent": intent, "tool": tool.name, "input": pname,
                   "question": question, "asks": asks}


# ======================= 1. INTENT =======================
def decide_intent(agent, sess):
    """[DECISION] Choice over the intents."""
    return agent.model.choice(build_state(agent, sess), "What does the user want?",
                              {n: s.desc for n, s in agent.intents.items()}, label="1. intent")


# ======================= 2a. TOOL =======================
def decide_tool(agent, sess, tools, context, calls):
    """[DECISION] Choice over the intent's tools + none."""
    options = {name: t.desc for name, t in tools.items()}
    options["none"] = ("No tool call is needed: the tool calls this turn already hold "
                       "everything needed, or no listed tool fits.")
    return agent.model.choice(build_state(agent, sess, context, calls),
                              "Which tool should be called next?", options, label="2a. tool")


# ======================= 2a2. OPTIONAL INPUTS =======================
def decide_input_needed(agent, sess, intent, tool, pname, context):
    """[DECISION] Noul: does the current message give (or pick) this optional input?
    State: recent conversation from memory, at most 4 messages: min(k, 4), and 4 when
    k=None (so a pick like "the first one" can be understood without a long history),
    current message, classified intent + context, tool and input descriptions."""
    lines = _past(agent, sess, "Recent conversation:", 4)
    lines += [f"Current user message: {sess.history[-1][1]}",
              f"Intent: {intent} - {agent.intents[intent].desc}"]
    if context:
        lines.append(f"Context: {context}")
    lines += [f"Tool: {tool.desc}",
              f"Optional input {pname}: {tool.params[pname].desc}"]
    p = agent.model.noul("\n".join(lines),
                         f"Does the user's current message give or pick a specific {pname} for "
                         f"this tool call, either by naming it, by choosing one the agent just "
                         f"listed (for example 'the first one' or 'the dispatched one'), or by "
                         f"referring to the one just discussed (for example 'it', 'that one' or "
                         f"'this order')? Answer no if the current message neither names, picks "
                         f"nor refers to a specific {pname}, for example when it asks for all "
                         f"of them or gives no hint which one.",
                         label=f"2a2. optional {pname} given?")
    return p >= 0.5


# ======================= 2b. INPUTS =======================
def resolve_params(agent, sess, intent, tool, context):
    """Required inputs are always resolved. Optional inputs are resolved only if the
    current message gives them; otherwise they are left out and the tool's default is used."""
    args = {}
    for pname, param in tool.params.items():
        picked = False             # 2a2 said the user names or picks this optional input
        if param.optional and pname not in sess.slots:
            if not decide_input_needed(agent, sess, intent, tool, pname, context):
                continue
            picked = True
        try:
            args[pname] = resolve_param(agent, sess, tool, pname, context, picked)
        except _Ask as a:
            pause(agent, sess, intent, tool, pname, a.text)
            raise
    return args


def resolve_param(agent, sess, tool, pname, context, picked=False):
    """categories -> Choice; else regex on the current message -> (several matches) Choice;
    else, if the user picked an optional input (2a2 yes), regex on the agent's last message
    -> Choice (always a Choice, even for one match); else window -> Choice."""
    if pname in sess.slots:
        return sess.slots[pname]
    param = tool.params[pname]

    if param.options:
        value = decide_option(agent, sess, tool, pname, param, context)
        if value is None:
            raise ask_for(pname, param)
        sess.slots[pname] = value
        return value

    exact = pname in sess.exact_wait
    if exact:
        sess.rejected.pop(pname, None)
        sess.attempts.pop(pname, None)
    rejected = sess.rejected.get(pname, set())

    matches = regex_candidates(sess, param)
    shown = (regex_candidates(sess, param, last_agent_message(agent, sess),
                              "the agent's last message")
             if picked and not matches else [])
    if matches:
        cands = [c for c in matches if c[0] not in rejected]
        value = cands[0][0] if len(cands) == 1 else (
            decide_span(agent, sess, tool, pname, cands, rejected, context) if cands else None)
    elif shown:                    # the user picked a value the agent just showed
        cands = [c for c in shown if c[0] not in rejected]
        value = decide_span(agent, sess, tool, pname, cands, rejected, context) if cands else None
    else:                          # optional inputs never come from history
        cands = [c for c in window_candidates(agent, sess, pname,
                                              with_previous=not (exact or param.optional))
                 if c[0] not in rejected]
        value = decide_span(agent, sess, tool, pname, cands, rejected, context) if cands else None

    if value is None:
        if rejected or exact:
            sess.exact_wait.add(pname)
        raise ask_for(pname, param)
    if exact:                      # typed after we asked: if rejected again, it doesn't exist
        sess.exact_wait.discard(pname)
        sess.exact.add(pname)
    sess.slots[pname] = value
    return value


def ask_for(pname, param):
    """The agent's question for a missing input, built from its description or categories."""
    name = pname.replace("_", " ")
    if param.options:
        opts = list(param.options)
        listed = ", ".join(opts[:-1]) + f" or {opts[-1]}" if len(opts) > 1 else opts[0]
        return _Ask(_render(MESSAGES["ask_option"], {"name": name, "options": listed}))
    return _Ask(_render(MESSAGES["ask_value"], {"name": name, "desc": param.desc}))


def _candidate(text, s, e):
    raw = text[s:e]
    return raw, raw, f"...{text[:s][-30:]}[{raw}]{text[e:][:30]}..."


def regex_candidates(sess, param, text=None, source=None):
    """Matches of the input's format in `text` (default: the current user message).
    [(value, raw, context)]; `source` is added to the context so the model knows where it
    was seen."""
    if not param.pattern:
        return []
    text = sess.history[-1][1] if text is None else text
    out, seen = [], set()
    for m in re.finditer(param.pattern, text):
        value, raw, ctx = _candidate(text, m.start(), m.end())
        if value not in seen:
            seen.add(value)
            out.append((value, raw, f"{ctx} (in {source})" if source else ctx))
    return out


def last_agent_message(agent, sess):
    """The agent's last reply, if the memory lets the model see it ("" with NoMemory)."""
    return next((t for r, t in reversed(agent.memory.messages(sess.history)) if r == "agent"), "")


def window_candidates(agent, sess, pname, with_previous=True):
    """Every 1..window-word span of the latest message, plus the last value that worked."""
    text = sess.history[-1][1]
    words = list(_WORD.finditer(text))
    out, seen = [], set()
    for n in range(1, agent.window + 1):
        for i in range(len(words) - n + 1):
            c = _candidate(text, words[i].start(), words[i + n - 1].end())
            if c[0] not in seen:
                seen.add(c[0])
                out.append(c)
    prev = sess.last.get(pname)
    if with_previous and prev is not None and prev not in seen:
        out.append((prev, str(prev), "(used earlier in this conversation)"))
    return out[:agent.max_candidates]


def decide_span(agent, sess, tool, pname, cands, rejected, context):
    """[DECISION] Choice over candidate spans + none. Returns the value or None."""
    by_key = {raw: value for value, raw, _ in cands if raw != "none"}  # option key = the text
    options = {raw: f'"{raw}" - {ctx}' for _, raw, ctx in cands if raw != "none"}
    options["none"] = "None of these is the value the user means."
    state = param_state(agent, sess, tool, pname, context)
    if rejected:
        state += f"\nAlready tried, the tool rejected them: {sorted(rejected)}"
    try:
        pick = agent.model.choice(state, f"Which candidate is the {pname} for this tool call?",
                                  options, label=f"2b. input {pname}")
    except LowConfidence:
        return None
    return by_key.get(pick)


def decide_option(agent, sess, tool, pname, param, context):
    """[DECISION] Choice over the input's categories + none. Returns the category or None."""
    options = dict(param.options)
    options["none"] = "The user did not state this."
    try:
        pick = agent.model.choice(param_state(agent, sess, tool, pname, context),
                                  f"Which {pname} does the user give?", options,
                                  label=f"2b. input {pname}")
    except LowConfidence:
        return None
    return None if pick == "none" else pick


def wrong_input(agent, sess, intent, tool, args, calls, context):
    """A tool rejected an input. Returns True if the turn should end (user-typed value)."""
    names = [n for n in args if not tool.params[n].options]  # categories can't be "wrong"
    if len(names) > 1:  # [DECISION] which input was wrong?
        names = [agent.model.choice(build_state(agent, sess, context, calls),
                                    "Which tool input was wrong?",
                                    {n: tool.params[n].desc for n in names},
                                    label="2c. wrong input")]
    for p in names:
        v = sess.slots.pop(p, None)
        if p in sess.exact:
            sess.exact.discard(p)
            return True
        sess.rejected.setdefault(p, set()).add(v)
        sess.attempts[p] = sess.attempts.get(p, 0) + 1
        if sess.attempts[p] >= agent.max_param_tries:
            sess.exact_wait.add(p)
            ask = ask_for(p, tool.params[p])
            pause(agent, sess, intent, tool, p, ask.text)
            raise ask
    calls[-1] = (tool.name, args, {"ignored": "wrong input value, another value is tried"})
    return False


# ======================= 2c. AFTER EACH TOOL CALL =======================
def decide_after_tool(agent, sess, outcomes, context, calls):
    """[DECISION] One request: Noul "another tool?", Noul "wrong input?", Choice outcome. (Question
    IDs have no spaces: some providers, e.g. Cloudflare Clef, only accept [A-Za-z0-9_.-].)"""
    p, outcome, conf = agent.model.nouls_and_choice(
        build_state(agent, sess, context, calls),
        {"another_tool": "Is another tool call needed to fully handle the user's request?",
         "wrong_input": "Does the latest tool output say an input value was wrong, invalid or "
                        "not found, so the same tool should be retried with a different value?"},
        "What is the outcome of this turn?",
        {n: o.desc for n, o in outcomes.items()},
        label="2c. after tool", choice_label="outcome")
    return p["another_tool"] >= 0.5, p["wrong_input"] >= 0.5, outcome, conf


def final(agent, outcome, conf):
    if conf < agent.model.min_conf:
        raise LowConfidence("outcome")
    return outcome


# ======================= TOOL LOOP (2a -> 2b -> tool -> 2c) =======================
def tool_loop(agent, sess, intent, spec, outcomes, resume_tool=None, trace=None, calls=None,
              approved=False):
    """tool -> inputs -> [middleware before_tool] -> run -> after-tool decisions -> repeat.
    Returns (calls, outcome).
    `resume_tool`: a paused call being continued; it runs first without step 2a.
    `trace`: a list that receives every tool call as {tool, inputs, output} the moment it
    runs, so the caller still has them if the turn stops to ask for something.
    `calls`: the tool calls already made this turn (when continuing after an approval).
    `approved`: the first call was approved by a person, so middleware does not stop it."""
    tools = {n: agent.tools[n] for n in spec.tools}
    context = spec.context
    calls, retry = list(calls or []), resume_tool
    skip_middleware = approved
    while len(calls) < agent.max_calls:
        name = retry or decide_tool(agent, sess, tools, context, calls)
        retry = None
        if name == "none":
            return calls, None
        tool = tools[name]
        args = resolve_params(agent, sess, intent, tool, context)
        if not skip_middleware:                    # may raise Interrupt: the tool does not run
            for mw in agent.middleware:
                mw.before_tool(agent, sess, intent, tool, args, calls)
        skip_middleware = False
        result = tool.run(**args)
        calls.append((name, args, result))
        if trace is not None:
            trace.append({"tool": name, "inputs": copy.deepcopy(args),
                          "output": copy.deepcopy(result)})

        another, wrong, outcome, conf = decide_after_tool(agent, sess, outcomes, context, calls)
        if wrong:
            if wrong_input(agent, sess, intent, tool, args, calls, context):
                return calls, final(agent, outcome, conf)
            retry = name                           # same tool, next candidate
            continue
        for p, v in args.items():
            sess.rejected.pop(p, None)
            sess.attempts.pop(p, None)
            sess.exact.discard(p)
            sess.last[p] = v
        if not another:
            return calls, final(agent, outcome, conf)
    return calls, None


# ======================= 3. OUTCOME =======================
def decide_outcome(agent, sess, outcomes, context, calls):
    """[DECISION] Choice over the intent's outcomes (when the loop exited early)."""
    return agent.model.choice(build_state(agent, sess, context, calls),
                              "What is the outcome of this turn?",
                              {n: o.desc for n, o in outcomes.items()}, label="3. outcome")
