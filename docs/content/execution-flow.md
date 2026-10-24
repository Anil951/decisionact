# Execution flow

[Documentation](../README.md) / Execution flow

This page describes the framework's current execution path, including candidates
from earlier tool outputs. The decision model answers typed
questions; Python code builds the choices, runs tools, manages session state,
and renders replies. **Choice** selects one supplied alternative. **Noul** judges
a yes/no condition. The diagram follows the paper's step names and numbering;
the sections below explain each decision and operation.

## Step-by-step execution

### Incoming message and session state

Your application calls `agent.turn(message, session_id)`. The framework loads the
session, appends the message, and supplies the previous messages allowed by the
memory configuration. Sessions live in Python memory by default; an explicit
checkpointer can save them elsewhere. A pending human approval is handled before
ordinary intent selection: approve, reject, or keep waiting.

### 0. Continue a paused input request

If a tool is waiting for an input, a Noul checks whether the new message answers
its question. A yes keeps the saved intent and tool and resumes input resolution
at step 2b, skipping intent and tool selection. A no discards the paused
call and starts a new request. Without a pending question, execution goes
directly to intent selection.

### 1. Select one intent

A Choice selects among the configured intent names using their descriptions,
the current message, and supplied history. The selected intent restricts which
tools and outcomes are available. Its context guides subsequent decisions.
If the intent has no tools, skip the loop and go directly to outcome resolution.

### 2a. Select the next tool

A Choice selects from the intent's permitted tools and `none`. Its state includes
the request, intent context, and tool calls already made in this turn. A tool
selection enters input resolution; `none` exits the loop and goes to the outcome.
`max_calls` defaults to `6` tool executions per turn, including retries. Configure
it when creating your agent: [configure the tool-call limit](api-reference.md#tool-call-limit).

### 2a2. Check optional inputs

For each unresolved optional input, a Noul asks whether the user supplied or
referred to a value. If yes, resolve it like a required input. If no, omit the
argument so the function's Python default applies, then continue to the next
parameter. Execute only after all parameters have been handled. Required inputs always go
through resolution. This check can use up to four previous messages when the
memory configuration permits them.

### 2b. Resolve inputs

The expanded diagram repeats this path for every parameter of the selected tool.
It skips straight to execution if the tool has no parameters. For each parameter:

1. Reuse its already resolved value, if present.
2. If optional, run the presence Noul; an absent value uses the Python default and
   returns to the parameter loop.
3. If it declares categories, select from their keys and descriptions plus `none`.
4. Otherwise, collect eligible values from earlier tool outputs in this turn,
   then try regex matching. Merge matches with output candidates, remove
   duplicates and exclude rejected values. One remaining current-message match
   binds directly only when no output candidates were collected. Otherwise use
   candidate Choice, even when only one merged value remains.
5. Without a pattern or current-message matches, try shown-reply matches where
   supported or bounded word-span candidates, then merge output candidates.
   Select with Choice, or ask if no usable value can be selected.
6. Store the resolved value and return to the next parameter. Execute the tool
   only once every required or supplied optional input is ready.

Reuse already resolved values when present. For categorical inputs, a Choice
selects a declared option or `none`. For text inputs, code builds candidates from
regex matches or bounded message spans and merges eligible earlier tool-output
values. Supported paths can also offer a previous successful value or values
shown in the last visible agent reply. Choice includes each candidate's text
context or its source tool call and output path.

Output candidates include scalar strings and numbers from nested output objects
and lists. Error/ignored outputs, booleans and empty values are excluded. A
declared regex must match the whole output value. Output candidates are skipped
when the agent has asked for an exact value. `max_candidates` also caps the
collected output candidates.

If no usable value is selected, return a clarification question and retain the
paused call. The next message returns to the continuation check. Input conversion and business
validation remain the tool's responsibility.

### Execute tool

Once inputs are ready, run `before_tool` middleware. Human approval can interrupt
execution and save the pending call before the function runs. Approval resumes
that call; rejection skips it and selects the configured rejection outcome.

If execution is permitted, call the Python function and record its arguments and
output. The tool wrapper converts ordinary function exceptions into error
dictionaries. Calls execute sequentially.

### 2c. Inspect result

One model request asks two Nouls—whether an input was rejected and whether another
tool is needed—and a Choice over the intent's outcomes. Handle the answers in
this order:

1. **Repair a rejected input:** Exclude the rejected candidate and retry the same
   tool with another value, retaining other resolved inputs. Input-retry limits
   can trigger a question asking for the exact value. `max_param_tries` defaults
   to `3`; it counts tool-rejected values for an input, rather than every tool
   error. A missing or low-confidence value can cause a question immediately.
2. **Continue the loop:** If no input repair is needed but another call is needed,
   return to step 2a to select the next tool.
3. **Finish:** Otherwise, accept the outcome if its confidence meets the threshold
   and proceed to outcome resolution.

When `max_calls` is reached, the loop stops and proceeds to outcome selection.
Reaching the limit does not mean the user's task is complete.

### 3. Resolve the outcome

Use the accepted outcome from step 2c when available. Otherwise, make a Choice
over the selected intent's allowed outcomes. If only one outcome is possible,
select it without an additional model call.

### Render reply and return

Fill the outcome's predefined reply template with available tool inputs and
dictionary output fields. Append the reply to history, save the session, and
return `TurnResult` with the reply, intent, outcome, and decision and tool traces.
The framework does not generate a free-form reasoning paragraph or reply.

## A normal turn

The following independent script shows the public entry point. Set
`TYPESAFE_API_KEY` before running it; no tutorial definitions are imported:

```python
import os
from decisionact import Agent, Intent, Outcome
from decisionact.models import SystemOneModel


if __name__ == "__main__":
    agent = Agent(
        tools=[],
        intents={
            "greeting": Intent(desc="The user says hello", outcomes=["welcome"]),
            "other": Intent(desc="Requests unrelated to greetings", outcomes=["help"]),
        },
        outcomes={
            "welcome": Outcome(desc="A greeting was received", reply="Hello!"),
            "help": Outcome(desc="The request is outside this demo", reply="Try saying hello."),
        },
        model=SystemOneModel(api_key=os.getenv("TYPESAFE_API_KEY")),
    )
    result = agent.turn(message="Hello", session_id="flow-demo")
    print(result.reply)
```

With successful decisions, this replies `Hello!`. The example has no tools, so it
skips the tool loop. For any configured agent, the full turn path is: 

```text
Application: agent.turn(message, session_id)
  -> load Session and append the user message
  -> handle pending approval or continue a missing-input request, if present
  -> choose one intent
  -> choose an allowed tool
  -> resolve its parameters
  -> run middleware before_tool hooks
  -> execute the Python tool
  -> evaluate the result: another tool, wrong input, and candidate outcome
  -> repeat the tool loop if needed, within max_calls
  -> select the final outcome and render its reply template
  -> append the reply, save the Session, return TurnResult
```

There is no generated reasoning paragraph or generated reply step. Model requests
ask typed questions about state; the reply text comes from your templates or the
framework's configured fallback wording.

## Which function calls which?

These names explain the implementation; internal helpers are not a stable API
for applications to call directly.

| Stage | Calls in the implementation | Purpose |
| --- | --- | --- |
| Entry | `Agent.turn()` -> `Agent._load()` | Load saved data or create a Session; add the message. |
| Bookkeeping | `Agent._execute()` -> `Agent._handle()` | Start a decision trace and run the turn. |
| Continuation | `steps.decide_continue()` | Ask a Noul whether a message answers the last missing-input question. |
| Intent | `steps.decide_intent()` -> `model.choice()` | Select one key from the configured intents. |
| Tool loop | `steps.tool_loop()` -> `steps.decide_tool()` | Select an intent-allowed tool or `none`. |
| Inputs | `steps.resolve_params()` -> `steps.resolve_param()` | Resolve each required or supplied optional parameter. |
| Approval/hooks | `Middleware.before_tool()` | Permit the call or interrupt it before execution. |
| Execution | `Tool.run(**args)` -> your function | Execute the tool; ordinary exceptions become error output. |
| Evaluation | `steps.decide_after_tool()` -> `model.nouls_and_choice()` | Batch questions about another tool, incorrect input, and outcome. |
| Retry | `steps.wrong_input()` | Reject a candidate, retry within limits, or ask for an exact value. |
| Reply | `Agent._finish()` -> `steps.decide_outcome()` when needed | Choose the ending and render the predefined reply. |
| Storage | Python session snapshots, or explicit `Checkpointer.save()` | Retain the Session in process memory by default; save through a checkpointer only when supplied. |

An intent with no tools skips the tool loop. If only one final outcome is possible,
the framework can select it without another model call. A tool choice of `none`
also exits the loop and proceeds to the outcome.

## Resolving an input

For an optional input, `decide_input_needed()` asks a Noul first. If the current
message does not supply it, the tool's Python default is used.

For inputs that are needed:

1. Reuse a value already resolved for the current request, if available.
2. For categorical `options`, use a Choice over the category keys and `none`.
3. Otherwise, collect `output_candidates()` from earlier calls, then try
   `regex_candidates()` on the current message.
4. `merge_candidates()` deduplicates message/output values and filters rejected
   values. One remaining regex value binds directly only when no output candidates
   were collected; otherwise `decide_span()` makes a Choice, even for one value.
5. If an optional input refers to a shown value, candidates can come from the
   last visible agent reply.
6. Otherwise, `window_candidates()` builds word spans and, when allowed, the
   previous successful value for that parameter. Both this path and the shown-reply
   path merge output candidates before Choice.
7. If no usable value is selected, `ask_for()` and `pause()` record the question
   and end the turn with outcome `asking`.

The parameter `window` controls span length; `max_candidates` caps how many span
candidates are considered. Values preserve user text; regex extraction does not
replace validation inside your tool.

## Continue a missing-input request

A later `agent.turn(...)` loads the paused tool. `decide_continue()` decides whether
the new message answers its question. If yes, intent selection and the initial
tool selection are skipped; input resolution resumes. If not, the paused call is
dropped and a new intent is selected. Asking beyond `max_asks` ends with `stopped`.

## Continue an approval

```text
HumanInTheLoopMiddleware.before_tool()
  -> save pending tool, inputs, previous calls, and rejection outcome
  -> raise Interrupt
Agent._execute()
  -> return awaiting_approval and save the Session

Later: agent.turn('/approve', session_id)
  -> middleware.answer_interrupt() -> parse_command()
  -> Agent._decide_approval()
  -> execute the approved call without asking for the same approval again
  -> evaluate the tool result and finish the turn
```

`agent.resume(session_id, approve())` reaches the same continuation without adding
a user chat message. Rejection selects the configured rejection outcome without
running the tool. Later tools can still require their own approvals.

## Provider calls and errors

Both adapters use `DecisionModel.ask(state, questions)`:

- Jev translates question dictionaries into SDK objects, calls
  `TypeSafeClient.system_one()`, and converts answers back to dictionaries.
- Clef uses `HttpDecisionModel._send()` to POST the state and questions, then
  unwraps Cloudflare's result envelope.

`choice()`, `noul()`, `score()`, and `nouls_and_choice()` record their decisions
in the current turn's trace. Score is available as a helper; the current agent
loop uses Choice and Noul decisions.

`LowConfidence`, missing-input questions, and middleware interrupts have handled
turn paths. Model availability and other provider exceptions propagate to the
caller. They do not produce a normal fallback `TurnResult`, and the failed turn
does not reach the normal save step. The framework does not provide automatic
provider retries or a transaction that rolls back external tool effects. Check
the actual tool effects before retrying a request after a provider failure.

See [API reference](api-reference.md) for public signatures and limitations.
