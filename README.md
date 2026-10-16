# DecisionAct

### Every action Is a Decision:<br>Decision-Model-Driven Execution for Structured Agent Workflows

DecisionAct is an agent framework written in Python. A decision model selects
an intent, tools, inputs, and an outcome using typed questions. Your Python functions
perform the actions, and predefined reply templates produce the response.

Supported providers are **TypeSafe Jev** (`SystemOneModel`) and **Cloudflare Clef**
(`CloudflareModel`).

The current version implements **single-agent, single-intent workflows**: one agent
handles one intent per message. Future versions are planned to support
**single-agent, multi-intent workflows** and **multi-agent workflows**.

## Install locally

Requires Python 3.10 or newer. From this project folder:

### Using uv

With [uv installed](https://docs.astral.sh/uv/getting-started/installation/), install
the project and its Jev and example dependencies:

```bash
uv sync --extra jev --extra examples
```

For Clef only, use `uv sync --extra examples`.
uv creates and manages the project's `.venv` automatically.
Run the examples without activating it:

```bash
uv run --extra jev --extra examples python -m examples.order_agent
uv run --extra jev --extra examples python -m examples.flight_desk_agent
```

### Using pip

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -e ".[jev,examples]"
```

For Clef only, use `python -m pip install -e ".[examples]"`. The Jev SDK is optional
and loaded only when constructing `SystemOneModel`.

## A small agent

```python
import os
from decisionact import Agent, Intent, Outcome, Param, tool
from decisionact.memory import ConversationBufferMemory
from decisionact.models import SystemOneModel

@tool(order_id=Param("Order ID, for example A1234", pattern=r"\b[A-Z]\d{4}\b"))
def get_order(order_id):
    """Return an order's delivery status."""
    return {"order_id": order_id, "status": "dispatched"}

agent = Agent(
    tools=[get_order],
    intents={
        "status": Intent(
            "Check an order's delivery status",
            tools=["get_order"], outcomes=["status"]),
        "other": Intent("Any other request", outcomes=["help"]),
    },
    outcomes={
        "status": Outcome("Order status returned", "Order {order_id} is {status}."),
        "help": Outcome("Outside order tracking", "Please ask about an order's status."),
    },
    model=SystemOneModel(api_key=os.environ["TYPESAFE_API_KEY"]),
    memory=ConversationBufferMemory(k=7),
)

result = agent.turn("Where is A1234?", session_id="customer-1")
print(result.reply)
print(result.intent, result.outcome, result.tool_calls)
```

Tools run locally. The state sent to the provider can include messages, tool inputs,
and tool outputs. Model decisions are probabilistic; evaluate your intents and
confidence thresholds with representative requests.

## Select Jev or Clef

```python
from decisionact.models import SystemOneModel, CloudflareModel

jev = SystemOneModel(api_key="YOUR_TYPESAFE_KEY", model="jev-latest")
clef = CloudflareModel(
    api_token="YOUR_CLOUDFLARE_TOKEN",
    account_id="YOUR_ACCOUNT_ID",
    model="clef",  # or a supported Clef variant such as clef-flash
)
# Pass the chosen instance as Agent(..., model=jev) or model=clef.
```

Both adapters accept `min_conf` (default `0.6`) and `timeout` (default 30 seconds).
Low-confidence Choice answers produce the rephrase response. Provider access and
model availability depend on your account. No model weights are bundled.

## Run the examples

Both examples use Jev directly. Copy `.env.example` to `.env` in this project
folder and set `TYPESAFE_API_KEY`. Each example loads this key and initializes
`SystemOneModel` itself. Keep `.env` out of Git. Run from this folder:

```bash
python -m examples.order_agent
python -m examples.flight_desk_agent
```

Each example has its own input loop and uses the default session ID; edit the
call to `agent.turn()` if you need separate conversations. File-based SQLite
checkpoint configuration is commented out. Uncomment the import and `checkpointer`
argument to save conversations across restarts.

### Order agent

Checks and lists orders, and cancels eligible orders after human approval.

- `Show my orders`
- `Where is B5678?`
- `Cancel A1234 because I changed my mind`
- `/approve` or `/reject Keep the order`

Sample orders: A1234 is placed, B5678 is dispatched, C9012 is delivered.

### Flight desk agent

Searches flights, books tickets, checks bookings, changes dates, cancels bookings,
adds baggage, and assigns seats. It demonstrates categorical and optional inputs,
follow-up questions, and references to previous results.

- `Show my bookings`
- `Check booking BK1001`
- `Find flights from Delhi to Mumbai on YYYY-MM-DD` (supply a future date)
- `Add 5 kg baggage to BK1002`

BK1001 and BK1002 are confirmed; BK1003 is completed. Demo dates are relative to
the day the example starts. All inventory is fictional and kept in memory.
By default, restarting an example resets both inventory and conversation state. These examples perform no real orders, bookings, payments, or refunds.

## Memory and storage

Memory determines which past messages the model sees. Checkpoints save the full
conversation and working state, including missing-input pauses and approvals.

```python
from decisionact.memory import NoMemory, ConversationBufferMemory
from decisionact.checkpoint import SqliteCheckpointer

memory = ConversationBufferMemory(k=7)  # recent messages; k=None keeps all
storage = SqliteCheckpointer("chat.db")
# Agent(..., memory=memory, checkpointer=storage)
```

SQLite is the only built-in storage backend. Defaults are `NoMemory()` and
`SqliteCheckpointer(":memory:")`, which keeps sessions for the life of the agent.
Use a file path such as `SqliteCheckpointer("chat.db")` to persist sessions across
restarts. You can use
`agent.history(session_id)` and `agent.reset(session_id)` to inspect or clear a
conversation.
Custom storage subclasses `Checkpointer` and implements `load`, `save`, `delete`,
and `list`.

## Middleware and human approval

```python
from decisionact.middleware import Approval, HumanInTheLoopMiddleware, approve, reject

approval = HumanInTheLoopMiddleware(approvals={
    "cancel_order": Approval(
        rejected_outcome="cancel_rejected",
        waiting="Cancelling {order_id} needs approval.",
    )
})
# Define cancel_rejected in your agent's outcomes, then use middleware=[approval].
# agent.resume("customer-1", approve())
# agent.resume("customer-1", reject("Keep the order"))
```

The tool waits until approved. Rejection selects the configured outcome, whose
reply can include `{rejection_reason}`. Terminal examples accept `/approve` and
`/reject [reason]` from whoever is chatting. For a separate reviewer, enforce
reviewer access in your application and call `agent.resume()` there.

Custom middleware subclasses `Middleware` and implements `validate`,
`before_tool`, or `answer_interrupt` as needed.

## Results and limits

`agent.turn(message, session_id)` returns `TurnResult` with `reply`, `intent`,
`outcome`, `tool_calls`, `decisions`, `paused`, and `pending_approval`.
Missing inputs pause the call and ask the user to provide a value. A later
message can resume that request or start a new one.

Agent limits default to `max_calls=6`, `max_param_tries=3`, `max_candidates=40`,
`window=3`, and `max_asks=2`. They are configurable keyword arguments.
Use distinct session IDs for distinct conversations. Serialize turns for the same
session in your application to avoid overwriting concurrent state updates.

## Project structure

```text
decisionact/
|-- pyproject.toml
|-- README.md
|-- LICENSE
|-- .env.example
|-- examples/
|   |-- __init__.py
|   |-- order_agent.py
|   `-- flight_desk_agent.py
`-- src/
    |-- __init__.py
    |-- main.py
    |-- steps.py
    |-- models/       # common interface, Jev, Clef
    |-- memory/
    |-- middleware/
    `-- checkpoint/   # SQLite
```

## License

DecisionAct is licensed under the [MIT License](LICENSE).
