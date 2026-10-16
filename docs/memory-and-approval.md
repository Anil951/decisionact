# Memory and approval

[Documentation](README.md) / Memory and approval

Use the expanded `my_order_agent.py` from [Building agents](building-agents.md).
It must contain both `get_order` and `cancel_order` before using this guide.

## Memory chooses what the model sees

```python
from decisionact.memory import ConversationBufferMemory, NoMemory

memory = ConversationBufferMemory(k=7)
```

Pass `memory=memory` when constructing an agent. `k=7` means the last seven
individual messages, counting user messages and agent replies separately. The
current user message is added separately to each decision's state.

`ConversationBufferMemory()` includes all past messages. `NoMemory()` is the
default and shows only the current message to the model. Optional-input detection
sees at most four previous messages, even with a larger buffer.

Memory is not storage: limiting the model's context does not delete saved history.
Memory helps the model interpret references such as "that order" but does not
guarantee the correct decision.

## SQLite stores the conversation

```python
from decisionact.checkpoint import SqliteCheckpointer

storage = SqliteCheckpointer("orders.db")
```

Pass `checkpointer=storage` to persist history, parameter state, paused inputs, and
pending approvals. SQLite is included with Python. Without an explicit checkpointer,
each agent creates its own `SqliteCheckpointer(":memory:")`.

File-based state survives restarts. Your order data does not: the guide's `ORDERS`
dictionary is reset when its module is loaded in a new process. Production tools
should store their business data separately.

Reuse a session ID to continue a conversation; use distinct IDs for different
customers. Serialize turns for the same session in your application.

## Add human approval

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
        "A reviewer declined cancellation",
        "Order {order_id} was not cancelled: {rejection_reason}.",
    )
    approval = HumanInTheLoopMiddleware(approvals={
        "cancel_order": Approval(
            rejected_outcome="cancel_rejected",
            waiting="Cancelling {order_id} needs approval.",
        )
    })
    storage = SqliteCheckpointer("orders.db")
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
            "Cancel A1234 because I changed my mind", session_id="approval-demo"
        )
        print(result.reply)
        if result.pending_approval:
            print(result.pending_approval.inputs)
            # This demo acts as the reviewer. A real application authenticates its reviewer.
            result = agent.resume("approval-demo", approve())
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

## Approve, reject, or wait

The following are alternatives while a tool is pending; do not approve and reject
the same pending call. They assume the `agent` constructed above is available:

```python
from decisionact.middleware import reject

pending = agent.pending_approval("approval-demo")
if pending:
    print(pending.tool, pending.inputs, pending.actions)
    result = agent.resume("approval-demo", reject("Keep this order"))
```

The rejected tool does not execute. Its input values and `{rejection_reason}` are
available to the rejection template.

Alternatively, a chat interface can send commands through the normal turn API:

```python
# Send one of these only when a call is waiting for approval.
result = agent.turn("/approve", session_id="approval-demo")
# Or: agent.turn("/reject Keep this order", session_id="approval-demo")
```

Command matching is case-insensitive and uses no model. Other messages return
the waiting reply without executing the tool. These commands do not authenticate
the sender: anyone who can send messages to that session can answer. Use application
access controls and a separate reviewer flow when approval must be restricted.

## History, reset, and shutdown

```python
history = agent.history("approval-demo")  # list of (role, text) tuples
agent.reset("approval-demo")             # deletes only this conversation's state
```

Reset does not undo tools or change `ORDERS`. Closing a checkpointer releases its
database connection; do so only after all agents using it have finished.

## Custom middleware

Subclass `Middleware` to validate configuration, inspect a tool before it executes,
or interpret messages while a tool is waiting. This standalone declaration can be
passed as `middleware=[ToolNames()]`:

```python
from decisionact.middleware import Middleware

class ToolNames(Middleware):
    def before_tool(self, agent, sess, intent, tool, args, calls):
        print("Running tool:", tool.name)
```

Hooks run in configured order. Returning normally from `before_tool` permits
execution; raising `Interrupt(reply)` stops it. A custom interrupt also needs a
corresponding persisted state and continuation mechanism; the built-in approval
middleware implements those for approval requests.

Next: [Execution flow](execution-flow.md).
