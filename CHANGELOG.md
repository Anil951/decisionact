# Changelog

## v0.1.1

- Checkpointing is disabled by default. Omitting `checkpointer` or passing
  `checkpointer=None` no longer creates an in-memory SQLite database.
- Conversations, collected inputs, missing-input follow-ups, and pending approvals
  remain in Python memory for the lifetime of the agent instance. Explicit
  checkpointers continue to support persistence.
- Replace MkDocs with responsive React documentation, including search, light and
  dark themes, copyable code snippets, and an updated execution-flow diagram.
- Include the documentation website in package metadata and the PyPI README.

### Upgrading from v0.1.0

Sessions without an explicit checkpointer are still temporary and are lost when
the agent instance is discarded or the process restarts. `agent.checkpointer` is
now `None` in this mode. If your application directly accesses that attribute,
handle `None` or pass a checkpointer explicitly. `agent.history()`, `agent.reset()`,
follow-ups, and approvals continue to work without checkpointing.

## v0.1.0

- Initial release: single-agent, single-intent workflows; Jev and Cloudflare Clef
  decision models; Python tools and parameters; intents, outcomes, and reply
  templates; conversation memory; SQLite checkpoints; and human approval middleware.
