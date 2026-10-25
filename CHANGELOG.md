# Changelog

## v0.1.2

- **Repeated tool calls:** Previously, later calls could reuse earlier inputs.
  Each invocation now resolves fresh inputs using the current request and call history.
- **Dependent calls:** Earlier results were not offered as input choices. They are
  now selectable, allowing sequences such as `add(4, 5)=9`, then `add(9, 7)=16`.
- **Execution guidance:** Applications previously repeated general tool-loop rules
  in intent context. The framework now supplies guidance for order, dependencies
  and repeated operations automatically.
- **Clearer state:** Messages, intent context and tool observations now have separate
  JSON fields, helping the model distinguish instructions from completed results.
- **Approval continuation:** With `NoMemory`, approving a call previously hid the
  original request. New approval records now retain it for decisions and input
  extraction across repeated approvals and checkpoint restores.
- **Input-confidence recheck:** An uncertain input previously caused an immediate
  question. It now gets one recheck with the same choices and threshold before asking.
- **Confidence threshold:** Reduced the default Choice confidence requirement from
  `0.6` to `0.5`. Explicit `min_conf` settings still override the default.
- **Longer requests:** Previously, `max_calls=6` stopped execution after six calls.
  It now allows renewable groups of six, with a separate hard cap of
  `max_call_limit=24`. Extensions retain previous calls and the execution count.
- **Honest limit replies:** Limit stops could previously reach a success outcome.
  They now return `limit_reached`, an unfinished-work reply and `limit_reason`.
- **Documentation:** The calculator agent includes sample messages demonstrating
  multiple tool calls, with expected call steps and results. Updated the execution
  chart and related guides for v0.1.2.

### Upgrading from v0.1.1

- **Upgrade:** To retain the previous hard six-call ceiling, set both `max_calls=6`
  and `max_call_limit=6`. Handle `limit_reached` in your application.
- **Remaining limits:** Model choices can still be wrong. This remains one intent
  per request; interrupted chains are not fully preserved, and reply templates
  show the last matching result rather than automatically combining all results.

## v0.1.1

- **Changed — Default session storage:** v0.1.0 automatically created an in-memory
  SQLite database even when no checkpointer was configured. v0.1.1 stores history,
  collected inputs, paused questions, and pending approvals directly in Python
  memory instead. The `checkpointer` parameter now defaults to `None`: omitting it
  or passing `checkpointer=None` creates no checkpointer, SQLite connection, or
  database. Neither default saves sessions across process restarts. Pass a
  file-based SQLite checkpointer explicitly when you need persistence.

`ConversationBufferMemory` is unchanged: it chooses which previous messages the
model sees. It does not create a database or enable persistence; session storage
is handled separately.

### Upgrading from v0.1.0

`agent.checkpointer` is now `None` when no checkpointer is supplied. Handle `None`
if you access this attribute directly. History, reset, follow-ups, and approvals
still work within the same agent instance; sessions are lost when it is discarded
or the process restarts unless a file-based checkpointer is configured.

## v0.1.0

Initial release with the following features:

- **Agent workflows:** Single-agent, single-intent execution with input resolution,
  multiple tool calls, and outcome selection. Each turn returns a reply, selected
  intent and outcome, and tool-call details.
- **Decision models:** Jev and Cloudflare Clef adapters with configurable models,
  confidence thresholds, and request timeouts.
- **Python tools:** Register functions with `@tool`, using docstrings as tool
  descriptions. Execute resolved arguments and return results for replies;
  ordinary function exceptions become error dictionaries.
- **Parameters:** Describe inputs with `Param`, including text extraction, regex
  candidates, fixed categorical choices, and optional inputs with Python defaults.
- **Follow-up questions:** Ask for missing required inputs and resume the paused
  tool call when the user answers in the same session.
- **Intents:** Define request categories with descriptions, context, allowed tools,
  and possible outcomes. Support both tool-based requests and direct replies.
- **Outcomes and replies:** Define success, failure, or other endings with reply
  templates populated from resolved inputs and tool output fields.
- **Conversation memory:** Supply no history, a limited message buffer, or all
  previous messages to the model. Separate conversations by session ID, inspect
  history, and reset session state.
- **SQLite checkpoints:** Save history, collected inputs, paused questions, and
  pending approvals. Use in-memory SQLite by default or a file-based checkpointer
  to retain sessions across restarts.
- **Middleware and human approval:** Pause selected tool calls before execution.
  Approve to continue or reject with a reason and a configured outcome, through
  `agent.resume()` or session approval commands.
