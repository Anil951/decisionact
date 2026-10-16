# Execution flow

[Documentation](README.md) / Execution flow

This page traces the current implementation. Your application calls the public
methods; the framework calls the internal helpers. Internal names below explain
the source and are not a stable API to call from applications.

## A normal turn

Your application starts with:

```python
result = agent.turn("Where is A1234?", session_id="customer-1")
```

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
| Storage | `Checkpointer.save()` | Save the current Session after a normally completed or handled turn. |

An intent with no tools skips the tool loop. If only one final outcome is possible,
the framework can select it without another model call. A tool choice of `none`
also exits the loop and proceeds to the outcome.

## Resolving an input

For an optional input, `decide_input_needed()` asks a Noul first. If the current
message does not supply it, the tool's Python default is used.

For inputs that are needed:

1. Reuse a value already resolved for the current request, if available.
2. For categorical `options`, use a Choice over the category keys and `none`.
3. Otherwise, try `regex_candidates()` on the current message.
4. Multiple matches require a model Choice through `decide_span()`.
5. If an optional input refers to a shown value, candidates can come from the
   last visible agent reply.
6. Otherwise, `window_candidates()` builds word spans and, when allowed, the
   previous successful value for that parameter.
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
