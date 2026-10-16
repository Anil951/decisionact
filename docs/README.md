![DecisionAct - Every Action Is a Decision](assets/decisionact_white_banner.png)

# DecisionAct documentation

**Every Action Is a Decision**

DecisionAct is a Python agent framework that uses decision models to choose
intents, tools, inputs, and outcomes. Python functions execute the tools, and
predefined templates produce the replies.

These guides describe the v0.1.0 API in this repository. This version supports
single-agent, single-intent workflows: a message selects one intent, which can
involve several tool calls. Multi-intent and multi-agent workflows are planned.

## Start here

| Guide | What you will learn |
| --- | --- |
| [Quickstart](quickstart.md) | Install DecisionAct and run a small order-status agent. |
| [Building agents](building-agents.md) | Configure Jev or Clef and define tools, parameters, intents, and replies. |
| [Memory and approval](memory-and-approval.md) | Add conversation memory, SQLite storage, and human approval. |
| [Execution flow](execution-flow.md) | Follow the functions called during a turn and its continuation paths. |
| [API reference](api-reference.md) | Look up signatures, defaults, return values, and exceptions. |

Read the guides in order to build up one small order agent. Each code block states
whether it is a complete file or an addition to an earlier example.

## Repository examples

- [Order support](https://github.com/Anil951/decisionact/blob/main/examples/order_agent.py): order lookup, listing, cancellation,
  and approval.
- [Flight desk](https://github.com/Anil951/decisionact/blob/main/examples/flight_desk_agent.py): flight search, booking, changes,
  cancellation, baggage, and seats.

Both examples use fictional, in-memory business data. Their model requests use
your provider account. API credentials are not included with the package.

The installed library is imported as `decisionact`, even though this repository
keeps its implementation directly in [`src/`](https://github.com/Anil951/decisionact/tree/main/src/). Install the package before
running the examples; adding `src` to `PYTHONPATH` is not equivalent to installing
this layout.

[Back to the project README](https://github.com/Anil951/decisionact/blob/main/README.md)
