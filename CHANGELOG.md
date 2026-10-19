# Changelog

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
