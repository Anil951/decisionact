# API reference

[Documentation](../README.md) / API reference

This reference covers the public API in the repository's v0.1.2 implementation.
Python signatures determine which arguments are required. Examples below are small
fragments; names such as `agent`, `model`, and `INTENTS` refer to objects built in
the [quickstart](quickstart.md) or [approval guide](middleware-and-approval.md).

## Agent

Import from `decisionact`:

```text
Agent(
    tools, intents, outcomes, model, *,
    max_calls=6, max_call_limit=24, max_param_tries=3, max_candidates=40,
    window=3, max_asks=2,
    memory=None, checkpointer=None, middleware=None,
)
```

| Argument | Meaning |
| --- | --- |
| `tools` | List of functions decorated with `@tool`. |
| `intents` | Dictionary mapping intent names to `Intent` objects. |
| `outcomes` | Dictionary mapping outcome names to `Outcome` objects. |
| `model` | A `DecisionModel` instance, such as `SystemOneModel` or `CloudflareModel`. |
| `memory` | A `Memory` instance; defaults to `NoMemory()`. |
| `checkpointer` | Optional `Checkpointer`. Omitted or `None` disables checkpointing; sessions stay in Python memory for that agent instance. |
| `middleware` | Iterable of `Middleware` instances, called in order; defaults to none. |
| `max_calls` | Tool executions per allowance before checking whether to extend. Default: `6`. |
| `max_call_limit` | Absolute total tool executions, including retries. Default: `24`; must be at least `max_calls`. |
| `max_param_tries` | Rejected candidate values per input before asking for an exact value. |
| `max_candidates` | Caps word-span candidates and the separately collected distinct output candidates per parameter. Default: `40`; it is not a combined cap on every candidate source. |
| `window` | Maximum number of words in a candidate span. |
| `max_asks` | Maximum missing-input questions for the same paused input before stopping. |

All limits must be positive integers; booleans are rejected. Construction
validates registered tools, intent/outcome objects, referenced names, and middleware.
Invalid configuration raises `TypeError` or `ValueError`. It does not make a model
request. Business-rule checks belong inside your tools.

### Tool-call limit

`max_calls` sets the size of a call allowance across all tools, including retries.
It defaults to `6`. If more work is requested after that allowance is used, a Noul
receives the user message, intent context, complete current execution trace, and
budget counters, and decides whether to grant another allowance. Completed calls
are retained; only the allowance boundary advances.

`max_call_limit` is an absolute cap, defaulting to `24`. The model cannot extend
it. Change either value in your application's `Agent` constructor:

```python
agent = Agent(
    tools=TOOLS,
    intents=INTENTS,
    outcomes=OUTCOMES,
    model=model,
    max_calls=6,
    max_call_limit=24,
)
```

The final allowance is clipped to the remaining hard-limit capacity. No extension
is requested when the post-tool decision already indicates completion, including
completion on the last permitted call.

If further execution is needed at the hard cap, or an extension is declined, the
framework returns `outcome="limit_reached"` with an explicit unfinished-work reply.
`result.limit_reason` is `"hard_limit"` or `"continuation_declined"`. Ordinary
outcome selection does not turn these stops into success. Completed calls remain
in the trace; this does not add automatic continuation after a limit stop.

In v0.1.1, `max_calls` was the turn's execution ceiling. To preserve that ceiling
in v0.1.2, set `max_calls` and `max_call_limit` to the same value. Approval resumes
retain prior executions and the granted allowance; granting another allowance
does not clear the trace or reset the execution count.

### Repeated calls and decision state

One selected intent may invoke the same tool several times or mix its permitted
tools. New invocations resolve fresh inputs; wrong-input retries keep sibling
inputs, and paused calls keep partial inputs. JSON state separates
`framework_instructions`, `user_message`, `intent`, `conversation_history` and
`tool_calls_this_turn`. Each observation has `call_id`, `tool`, `arguments` and
`result`; input decisions also have `current_invocation` with the tool, input,
resolved sibling values, next call number and prior calls of that tool.

Eligible earlier output scalars become source-labelled input candidates, subject
to regex constraints and candidate limits. This is active-loop context, not a
durable action plan or duplicate-execution guard. State field details describe
the current implementation; applications should use public `TurnResult` fields
for traces. See [Calculator](calculator.md) and [execution flow](execution-flow.md).

Low-confidence text/categorical input selection gets one focused recheck with
unchanged choices and threshold. A confident `none`, or uncertainty after the
recheck, asks for the input. There is no new recheck configuration argument and
no matching recheck for intent/tool/outcome selection.

### `agent.turn(message, session_id="default")`

**Called by your application.** Takes a user message and returns `TurnResult` on a
normal or handled turn. The session ID selects the saved conversation. Approval
commands use this method too. A turn is synchronous and may make multiple blocking
provider requests.

```python
result = agent.turn(message="Where is A1234?", session_id="customer-1")
print(result.reply)
```

Provider exceptions propagate, including `DecisionModelNotFound` and other
`DecisionModelError` instances. These failures do not return a `TurnResult`.
Application/tool/storage errors can also propagate where they are not explicitly
handled by the implementation.

### `agent.resume(session_id, decision)`

**Called by your application or reviewer integration.** Takes `approve()` or
`reject(reason)` for a saved approval and returns `TurnResult`. Raises `ValueError`
if that session has no pending approval. Does not append a user message to history.

```python
from decisionact.middleware import approve

result = agent.resume(session_id="customer-1", decision=approve())
```

This is for human approval, not missing-input continuation. To supply a missing
parameter, send another message through `turn()`.

New pending approvals retain the original request for resumed decisions and input
extraction, independently of conversation memory. This applies to both `resume()`
and chat approval commands, repeated approval pauses and checkpoint restoration.
The request is stored in saved approval data; the public `PendingApproval` fields
are unchanged. Older records without it remain readable with legacy message behavior.

### `agent.pending_approval(session_id="default")`

Returns `PendingApproval` or `None`, without making a model request.

### `agent.history(session_id="default")`

Returns a list of `(role, text)` tuples. Roles are `user` and `agent`. A new or
reset session has an empty history, regardless of how much memory the model sees.

### `agent.reset(session_id="default")`

Deletes that session from Python memory or the explicit checkpointer and returns `None`. Does not undo tools,
clear business data, or delete other sessions.

## Tools, inputs, intents, and outcomes

Import these from `decisionact`:

```python
Param(desc, pattern=None, options=None, optional=False)
tool(fn=None, **params)
Tool(name, fn, desc, params)
Intent(desc, context="", tools=[], outcomes=[])
Outcome(desc, reply)
```

The list defaults shown for `Intent` are independent lists per instance.

| API | Purpose and return value |
| --- | --- |
| `Param` | Describes one input. `pattern` is a regex; `options` maps category names to descriptions. |
| `@tool(...)` | Returns the original function and attaches its specification as `function.tool`. |
| `Tool` | Holds a registered function and its input specification. Usually created by `@tool`. |
| `Tool.run(**args)` | Called by the framework. Returns the function's result or `{"error": str(exception)}` for an ordinary tool exception. |
| `Intent` | Describes a request, its context, allowed tool names, and possible outcome names. Requires at least one outcome when registered with an agent. |
| `Outcome` | Describes an ending and its predefined format-string reply. |

`@tool` requires a docstring, matching input names, nonempty descriptions, and a
Python default for optional inputs. It rejects simultaneous `pattern` and `options`.
Common declaration errors raise `TypeError`.

An input's type annotation does not cast its value. A regex may supply candidates;
it is not a guarantee that only regex matches reach the tool. Tool functions should
validate values and return useful error data when an action cannot be performed.

Template placeholders use tool inputs and top-level output fields. Missing keys
become empty strings. Lists become bullet lines. Normal Python formatting errors
are not automatically repaired.

## TurnResult

Imported from `decisionact`. Returned by `turn()` and `resume()`; applications
normally do not construct it manually.

| Field | Default | Meaning |
| --- | --- | --- |
| `reply` | Required when constructing | Text for the user. |
| `intent` | `None` | Selected intent, if one was selected. |
| `outcome` | `None` | Selected outcome or a framework status. |
| `tool_calls` | `[]` | Entries with `tool`, `inputs`, and `output`, in execution order. |
| `decisions` | `[]` | Model decision entries, including step/type/answer and confidence where applicable. |
| `paused` | `None` | Saved missing-input request, if any. |
| `pending_approval` | `None` | `PendingApproval`, if a tool is waiting for review. |
| `limit_reason` | `None` | `hard_limit` or `continuation_declined` when execution stops at a call allowance or cap. |

Special outcome values are `rephrase`, `asking`, `stopped`, `limit_reached`, and
`awaiting_approval`. There is no `error` field or automatic failed-turn recovery API
in this version. `reply` can be printed directly; printing the whole dataclass
shows the other fields too.

## Model adapters

Import from `decisionact.models`:

```python
SystemOneModel(
    api_key=None, model="jev-latest", base_url=None,
    min_conf=0.5, timeout=30.0,
)

CloudflareModel(api_token=None, account_id=None, model="clef", **kw)
```

`SystemOneModel` uses `typesafe_sdk`. `base_url` optionally selects a compatible
endpoint. `CloudflareModel` uses `httpx`; its `**kw` accepts `min_conf=0.5` and
`timeout=30.0`. Timeout values are in seconds. Both require provider credentials
for actual requests; Clef additionally requires an account ID.

Use `min_conf` between `0` and `1`. It gates Choice decisions, not Noul decisions.
The implementation does not perform comprehensive configuration or provider-answer
validation. Use valid settings and evaluate model behavior before production use.

### DecisionModel and HTTP base

```python
DecisionModel(model, min_conf=0.5)
HttpDecisionModel(model, url, headers, min_conf=0.5, timeout=30.0)
```

`DecisionModel` is the common provider interface. Custom adapters implement
`_send(state, questions)` returning an answers dictionary. `HttpDecisionModel`
implements the HTTP request; subclasses can override `_unwrap(body)` for a provider
envelope. These base classes do not choose a hosted model endpoint for you.

| Method | Arguments | Returns |
| --- | --- | --- |
| `ask(state, questions)` | State string and `{question_id: question_dict}`. | `{question_id: answer_dict}`; checks for missing answers. |
| `choice(state, question, options, label, min_conf=None)` | Options map names to descriptions; label names the trace step. | Selected option; raises `LowConfidence` below the threshold. |
| `noul(state, question, label)` | A yes/no question. | Probability of yes, as supplied by the provider. |
| `score(state, question, levels, label)` | Ordered rubric levels, starting at level zero. | `(score, confidence)`; score may be fractional. |
| `nouls_and_choice(state, noul_questions, choice_question, options, label, choice_label)` | Several named yes/no questions and one Choice. | `({name: probability}, choice, confidence)` in one request. |

The engine calls these methods automatically. You can also use them directly:

```python
choice = model.choice(
    state="The customer asks where an order is",
    question="Which request is this?",
    options={"status": "Order status", "cancel": "Order cancellation"},
    label="request type",
)
```

`nouls_and_choice()` returns Choice confidence without raising `LowConfidence`;
the engine checks it when accepting the final outcome. `ask()` itself does not add
a decision-trace entry. Helpers record entries through the exported `decision_log`
ContextVar while a turn is active; application code normally does not set it.

### Exceptions

| Exception | Meaning |
| --- | --- |
| `DecisionModelNotFound` | A subclass of `DecisionModelError`: missing/blank key or model name, mapped HTTP 401/403/404, or recognized credential/model messages in HTTP 400/422. The response can indicate permission or endpoint problems too. |
| `DecisionModelError` | Other wrapped provider failures, such as connection errors, HTTP errors, SDK failures, or missing requested answers. |
| `LowConfidence` | A Choice was below its threshold. `Agent` handles it as a rephrasing path; parameter resolution can instead ask for an input. |

For Clef, a missing account ID raises `ValueError`. A missing TypeSafe SDK raises
`ImportError`. Malformed JSON and unexpected response fields are not all normalized
to `DecisionModelError`; raw parsing or lookup exceptions may propagate. No model
error handlers are added to the repository examples.

## Memory

Import from `decisionact.memory`:

```python
Memory()
NoMemory()
ConversationBufferMemory(k=None)
```

`Memory` is an interface. Override `messages(history, limit=None)` to select previous
messages. Its `enabled` attribute is `True`; `NoMemory.enabled` is `False` and its
`messages()` always returns an empty list.

`ConversationBufferMemory.messages(history, limit=None)` excludes the current
message, then applies `k` and any smaller per-step limit. `k` is a positive integer
or `None`; invalid values raise `ValueError`. Counts are individual messages, not
user/agent pairs. The optional-input step imposes a maximum of four past messages.

## Checkpoints and Session

Import `Checkpointer` and `SqliteCheckpointer` from `decisionact.checkpoint`:

```python
SqliteCheckpointer(path, table="decisionact_sessions", timeout=10.0)
```

Use `":memory:"` for temporary storage or a filename for persistence. An invalid
table identifier raises `ValueError`. SQLite connection and serialization errors
can propagate. Saved values must be JSON-serializable.

| Method | Return value / effect |
| --- | --- |
| `load(session_id)` | Saved dictionary or `None`. |
| `save(session_id, data)` | Stores/replaces the JSON-ready dictionary; returns `None`. |
| `delete(session_id)` | Removes that session if present; returns `None`. |
| `list()` | List of saved session IDs; order is not guaranteed. |
| `close()` | Closes the SQLite connection. |

Custom storage subclasses `Checkpointer` and implements `load`, `save`, `delete`,
and `list`. The base interface does not require `close`.

`Session`, imported from `decisionact`, is the engine's working conversation state:
history, resolved/rejected inputs, retry counters, paused calls, approvals, and
previous successful values. `Session.to_dict()` returns checkpoint-ready data;
`Session.from_dict(data)` restores it and raises `ValueError` for an unsupported
format version. `Session.VERSION` is currently `1`. `resumed` is turn-local and is
not serialized. Applications normally use the Agent methods rather than mutating
Session objects directly.

## Middleware and approval

Import from `decisionact.middleware`:

```python
Middleware()
Interrupt(reply)
Approval(
    rejected_outcome,
    waiting="This needs a person's approval first. I'll continue once it is approved.",
)
HumanInTheLoopMiddleware(approvals)
Decision(approved, reason="")
approve()
reject(reason="no reason given")
parse_command(message)
```

`approvals` maps tool names to `Approval` objects. It must not be empty. Agent
construction validates the tool and rejection-outcome names; invalid rules raise
`TypeError` or `ValueError`. `waiting` is a template using available call values.

`approve()` returns `Decision(True)`. `reject(reason)` returns `Decision(False,
reason)`. `parse_command()` returns a Decision for `/approve` or `/reject [reason]`,
otherwise `None`. Matching is case-insensitive and performs no authorization.

### Hooks called by the framework

| Hook | When it runs | Return / behavior |
| --- | --- | --- |
| `validate(agent)` | Once after agent configuration is checked. | Return normally or raise a configuration error. |
| `before_tool(agent, sess, intent, tool, args, calls)` | After input resolution, before the function runs. | Return normally to permit execution; raise `Interrupt(reply)` to stop. |
| `answer_interrupt(sess, message)` | For a message received while approval is pending. | Decision if answered, otherwise `None`. |

`calls` contains previous `(tool_name, inputs, output)` tuples for the current
execution. Hooks run in middleware-list order. A plain `Interrupt` does not create
pending approval data by itself; `HumanInTheLoopMiddleware` saves that state before
raising it.

### PendingApproval

`PendingApproval(intent, tool, inputs, actions)` describes a waiting call. Access it
from `result.pending_approval` or `agent.pending_approval(session_id)`.

`actions` contains action/command dictionaries for approve and reject.
`PendingApproval.from_saved(saved)` reconstructs the object from checkpoint state
and returns `None` for no saved approval. The framework calls this automatically.

## Operational limits

- v0.1.2 handles one intent per message. There are no `multi_intent` or router arguments.
- Repeated-call input pairing, dependency selection and stopping are model
  decisions; shared operands and ambiguous references can still be mishandled.
- Trace call IDs do not implement idempotency or distinguish requested operations
  through a durable planner. A hard cap bounds executions, not semantic correctness.
- Missing-input continuation does not fully retain an interrupted multi-operation
  request and its call trace. A limit stop has no automatic continuation API.
- Later output fields overwrite earlier fields with the same name in reply
  templates. A successful action can be followed by an outcome-confidence fallback.
- Calls are synchronous. Serialize concurrent turns for the same session.
- Templates control wording; tools must enforce business rules and permissions.
- The database is not a transaction over external tool effects. A provider failure
  after a tool runs does not undo it or save an automatic recovery state. Review
  effects before retrying, and use idempotent tools where repeated execution matters.
- Default process-local sessions and fictional example business data do not survive
  a restart. File-based SQLite persists conversation state, not your tool's business data.

[Back to documentation](../README.md)
