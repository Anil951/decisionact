![DecisionAct - Every Action Is a Decision](../assets/decisionact_white_banner.png)

# DecisionAct documentation

[Preview and maintain the React documentation website](WEBSITE.md).

**Every Action Is a Decision**

DecisionAct is a Python agent framework that uses decision models to choose
intents, tools, inputs, and outcomes. Python functions execute the tools, and
predefined templates produce the replies.

These guides describe the v0.1.0 API in this repository. This version supports
single-agent, single-intent workflows: a message selects one intent, which can
involve several tool calls. Multi-intent and multi-agent workflows are planned.

## Get started

- [Overview](#decisionact-documentation)
- [Installation](content/installation.md)
- [Quickstart](content/quickstart.md)

## Core concepts

- [Tools](content/tools.md)
- [Parameters](content/parameters.md)
- [Intents](content/intents.md)
- [Outcomes](content/outcomes.md)
- [Decision models](content/models.md)
- [Memory and checkpoints](content/memory-and-checkpoints.md)
- [Middleware and human approval](content/middleware-and-approval.md)
- [Execution flow](content/execution-flow.md)

## Examples

- [Order support agent](content/order-agent.md)
- [Flight desk agent](content/flight-desk-agent.md)

## API reference

- [API reference](content/api-reference.md)

Core concept pages explain one feature at a time with independent examples.
Quickstart and example pages contain the complete application walkthroughs.

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
