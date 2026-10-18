# Quickstart

[Documentation](../README.md) / Quickstart

Build a small agent that checks an order's status. This example uses Jev and
fictional order data.

## Before you begin

Follow [Installation](installation.md) to install DecisionAct with pip or uv.
Use Python 3.10 or newer and a Jev provider API key for this example.

## 1. Set the API key

Set `TYPESAFE_API_KEY` in the terminal where you will run the script.

PowerShell:

```powershell
$env:TYPESAFE_API_KEY = "YOUR_TYPESAFE_API_KEY"
```

macOS or Linux:

```bash
export TYPESAFE_API_KEY="YOUR_TYPESAFE_API_KEY"
```

Use your own key and keep it out of source control. This guide reads the environment
directly; it does not require a `.env` file or `python-dotenv`.

## 2. Create the agent

Save this complete file as `my_order_agent.py`:

```python
import os

from decisionact import Agent, Intent, Outcome, Param, tool
from decisionact.models import SystemOneModel

ORDERS = {
    "A1234": {"item": "Headphones", "status": "placed"},
    "B5678": {"item": "Keyboard", "status": "delivered"},
}

ORDER_ID = Param(desc="Order ID, for example A1234", pattern=r"\b[A-Z]\d{4}\b")


@tool(order_id=ORDER_ID)
def get_order(order_id):
    """Look up an order's item and delivery status."""
    order = ORDERS.get(order_id)
    if order is None:
        return {"error": "Order not found", "order_id": order_id}
    return {"order_id": order_id, **order}


INTENTS = {
    "status": Intent(
        desc="Check an order's status",
        context="Look up the order once, then reply with its status or lookup error.",
        tools=["get_order"],
        outcomes=["status", "not_found"],
    ),
    "other": Intent(desc="Any request unrelated to order status", outcomes=["help"]),
}

OUTCOMES = {
    "status": Outcome(
        desc="The lookup returned an order and its status",
        reply="Order {order_id} ({item}) is {status}.",
    ),
    "not_found": Outcome(
        desc="The lookup returned an order-not-found error",
        reply="I could not find order {order_id}.",
    ),
    "help": Outcome(desc="The request is outside order tracking", reply="Ask me about an order's status."),
}


if __name__ == "__main__":
    model = SystemOneModel(api_key=os.getenv("TYPESAFE_API_KEY"))
    agent = Agent(
        tools=[get_order], intents=INTENTS, outcomes=OUTCOMES, model=model
    )
    result = agent.turn(message="Where is A1234?", session_id="customer-1")
    print(result.reply)
```

Run it:

```bash
python my_order_agent.py
```

With uv:

```bash
uv run python my_order_agent.py
```

With successful model decisions, the reply is:

```text
Order A1234 (Headphones) is placed.
```

Model decisions are probabilistic. A low-confidence decision can instead produce
a rephrasing request. Invalid credentials or an unavailable model can raise
`DecisionModelNotFound`.

## 3. Understand the calls

| Code | What happens |
| --- | --- |
| `Param(...)` | Describes one tool input. |
| `@tool(...)` | Attaches a tool specification to the ordinary Python function. |
| `Intent(...)` | Declares a request category and its allowed tools and outcomes. |
| `Outcome(...)` | Declares an ending and its reply template. |
| `SystemOneModel(...)` | Creates the Jev adapter; the request happens during a model call. |
| `Agent(...)` | Validates and stores your configuration. It does not run the tool. |
| `agent.turn(...)` | Loads the session, makes decisions, calls tools, renders a reply, and saves. |
| `result.reply` | Holds the final text to display. |

The code under the `__main__` guard runs when the file is launched directly.
Importing `my_order_agent` only defines the sample data, tool, intents, and outcomes,
so later guides can reuse them without starting a model request.

## 4. Inspect a turn

Add these lines after `result = agent.turn(...)` in the guarded block:

```python
print(result.intent)
print(result.outcome)
print(result.tool_calls)
print(result.decisions)
```

Tool traces show inputs and outputs; decision traces show the model's choices and
probabilities. Checkpointing is disabled by default. Conversations stay in plain
Python memory for the lifetime of that agent, without creating a SQLite database.

Next: [Tools](tools.md).
