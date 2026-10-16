# DecisionAct

### Every Action Is a Decision:<br>Decision-Model-Driven Execution for Structured Agent Workflows

DecisionAct is an agent framework written in Python. It uses decision models to
select intents, tools, inputs, and outcomes through typed questions. Your Python
code performs the actions, and predefined templates produce the replies.

**Decision models decide. Your code acts.**

## How it works

1. A user sends a message.
2. A decision model selects the intent from the options you define.
3. The framework selects an allowed tool and resolves its inputs.
4. Your Python function executes the action.
5. The model evaluates the tool result and selects the next step or outcome.
6. DecisionAct fills the selected reply template with the available results.

Missing required inputs lead to follow-up questions. Configured confidence
thresholds let the agent ask for a rephrasing when a decision is uncertain.

## Available in v0.1.0 (Latest version)

- **Single-agent, single-intent workflows:** one agent handles one intent per message.
- **Two decision-model providers:** TypeSafe Jev and Cloudflare Clef.
- **Typed decisions:** choice, yes/no probability (`Noul`), and rubric-based score.
- **Python tools:** declare ordinary functions with `@tool` and describe their inputs.
- **Parameter resolution:** required and optional inputs, categorical choices, and
  regular-expression or candidate-based extraction.
- **Explicit intents and outcomes:** define the available actions and reply templates.
- **Conversation memory:** choose no history or a configurable buffer of past messages.
- **SQLite checkpoints:** optionally save conversation state, missing-input pauses,
  and pending approvals to a file. The default SQLite database lives in memory.
- **Human approval middleware:** pause configured tool calls for approval or rejection.
- **Execution limits and traces:** bound tool calls and input retries, and inspect
  decisions, tool inputs, outputs, and outcomes through `TurnResult`.
- **Model availability errors:** `DecisionModelNotFound` identifies missing credentials
  or model names and provider-reported authentication or model-not-found failures.

## Why use DecisionAct?

DecisionAct is designed for structured workflows with known intents, tools, and
outcomes, such as order support and flight-desk operations.

The application defines the available choices and user-facing replies. The decision
model selects among those choices, while execution stays in Python functions. This
makes the permitted workflow and response wording easier to inspect and evaluate.

Compared with an agent that generates free-form replies, DecisionAct gives you
explicit response templates and bounded tool execution. LLM-based agents can also
use structured outputs, tool restrictions, and approval controls; the distinction
here is DecisionAct's decision-model-driven execution approach.

Decision quality still depends on the model, descriptions, confidence thresholds,
and tool implementation. Cost and latency depend on the provider and workload;
no universal performance advantage is claimed.

## Coming in future versions

- **Single-agent, multi-intent workflows:** handle several requests in one message.
- **Multi-agent workflows:** route requests between specialist agents and coordinate
  their execution.

These are planned features and are not included in v0.1.0.

## Examples

The `examples/` folder contains agents built using the DecisionAct framework:

- **Order agent:** checks order status, lists orders, and cancels eligible orders
  after approval.
- **Flight desk agent:** searches flights, books tickets, checks and changes bookings,
  cancels bookings, adds baggage, and selects seats.

Both examples use fictional data and demonstrate how tools, intents, outcomes,
and conversation memory fit together. Jev initialization is active, with a commented
Cloudflare Clef alternative.

## License

DecisionAct is licensed under the [MIT License](LICENSE).
