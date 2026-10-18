# Order support agent

This complete repository example shows DecisionAct tools, intents, outcomes,
conversation memory, and human approval using fictional business data.

## Capabilities

Look up one order or list orders, check status, and cancel eligible orders.
The cancellation tool validates the order state, and middleware requests human
approval before it executes.

- **Tools:** `get_order`, `cancel_order`.
- **Memory:** a conversation buffer keeps recent context available to decisions.
- **Approval:** approve or reject a pending cancellation.
- **Storage:** explicit SQLite initialization is commented out in the example;
  checkpointing is disabled and sessions stay in plain Python memory.

[View the complete order agent →](https://github.com/Anil951/decisionact/blob/main/examples/order_agent.py)

```text
Where is A1234?
Show my orders.
Cancel A1234 because I changed my mind.
/approve
```

The approval command applies only after a cancellation is waiting for approval.
The example’s reply depends on the model’s decisions and current demo data.

## Model setup

Both examples initialize Jev using the environment’s `TYPESAFE_API_KEY` and
include commented initialization for the Cloudflare Clef model. They also use
`python-dotenv` to load local environment settings; that helper is an example
dependency, not required by the minimal quickstart.

Never commit provider credentials. The fictional data resets when the example
process restarts; conversation checkpoints do not persist the business data.

## Extend the quickstart with cancellation

This optional walkthrough starts with the complete `my_order_agent.py` from the
[quickstart](quickstart.md). The declarations below are additions to that file,
not independent concept examples.

### Add the cancellation tool

Insert the following block into `my_order_agent.py` **above** its `__main__` guard.
It uses the imports, `ORDERS`, `ORDER_ID`, `INTENTS`, and `OUTCOMES` already defined there:

```python
@tool(
    order_id=ORDER_ID,
    reason=Param(
        desc="Why the customer wants to cancel",
        options={
            "changed mind": "The customer no longer wants the order",
            "delivery delay": "The delivery is taking too long",
            "other": "A different cancellation reason",
        },
    ),
)
def cancel_order(order_id, reason):
    """Cancel a placed order, with a reason; delivered orders cannot be cancelled."""
    order = ORDERS.get(order_id)
    if order is None:
        return {"error": "Order not found", "order_id": order_id}
    if order["status"] != "placed":
        return {"error": "Order cannot be cancelled", "order_id": order_id}
    order["status"] = "cancelled"
    return {"order_id": order_id, "status": "cancelled", "reason": reason}


INTENTS["cancel"] = Intent(
    desc="Cancel an order",
    context="Call cancel_order once. End with cancelled on success or cancel_failed on error.",
    tools=["cancel_order"],
    outcomes=["cancelled", "cancel_failed"],
)
INTENTS["other"] = Intent(
    desc="Any request unrelated to checking or cancelling orders", outcomes=["help"]
)
OUTCOMES["cancelled"] = Outcome(
    desc="cancel_order returned status cancelled",
    reply="Order {order_id} was cancelled: {reason}.",
)
OUTCOMES["cancel_failed"] = Outcome(
    desc="cancel_order returned an error",
    reply="Could not cancel order {order_id}: {error}.",
)
OUTCOMES["help"] = Outcome(
    desc="The request is outside order support", reply="I can check or cancel orders."
)
```

Update the `Agent(...)` call in the guarded block to register both tools:

```python
agent = Agent(
    tools=[get_order, cancel_order],
    intents=INTENTS,
    outcomes=OUTCOMES,
    model=model,
)
```

Replace the sample `agent.turn(...)` call with:

```python
result = agent.turn(message="Cancel A1234 because I changed my mind", session_id="customer-1")
print(result.reply)
```

With successful model decisions, the reply is:

```text
Order A1234 was cancelled: changed mind.
```

This version executes cancellation immediately. The [middleware and approval guide](middleware-and-approval.md) adds approval before cancellation.

## Add approval to cancellation

Save this complete file beside `my_order_agent.py` as `approved_order_agent.py`:

```python
import os

from decisionact import Agent, Outcome
from decisionact.checkpoint import SqliteCheckpointer
from decisionact.memory import ConversationBufferMemory
from decisionact.middleware import Approval, HumanInTheLoopMiddleware, approve
from decisionact.models import SystemOneModel
from my_order_agent import INTENTS, OUTCOMES, cancel_order, get_order


if __name__ == "__main__":
    outcomes = dict(OUTCOMES)
    outcomes["cancel_rejected"] = Outcome(
        desc="A reviewer declined cancellation",
        reply="Order {order_id} was not cancelled: {rejection_reason}.",
    )
    approval = HumanInTheLoopMiddleware(approvals={
        "cancel_order": Approval(
            rejected_outcome="cancel_rejected",
            waiting="Cancelling {order_id} needs approval.",
        )
    })
    storage = SqliteCheckpointer(path="orders.db")
    try:
        agent = Agent(
            tools=[get_order, cancel_order],
            intents=INTENTS,
            outcomes=outcomes,
            model=SystemOneModel(api_key=os.getenv("TYPESAFE_API_KEY")),
            memory=ConversationBufferMemory(k=7),
            checkpointer=storage,
            middleware=[approval],
        )
        result = agent.turn(
            message="Cancel A1234 because I changed my mind", session_id="approval-demo"
        )
        print(result.reply)
        if result.pending_approval:
            print(result.pending_approval.inputs)
            # This demo acts as the reviewer. A real application authenticates its reviewer.
            result = agent.resume(session_id="approval-demo", decision=approve())
            print(result.reply)
    finally:
        storage.close()
```

Run `python approved_order_agent.py`, or `uv run python approved_order_agent.py`.
On the normal path, the first turn has outcome `awaiting_approval` and the tool
has not run. `agent.resume(..., approve())` executes it and continues the outcome
decision. The rejection outcome belongs in the agent's outcomes dictionary but
does not need to be offered in `Intent.outcomes`.

Use a new session ID, or deliberately reset the demo session, when repeating the
example with a file that already holds conversation state.

## Related concepts

See [tools](tools.md), [parameters](parameters.md), [intents](intents.md),
[outcomes](outcomes.md), and [middleware](middleware-and-approval.md) for independent
concept examples. The [flight desk example](flight-desk-agent.md) applies the same
framework to a different workflow.
