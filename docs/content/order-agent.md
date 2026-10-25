# Order support agent

This agent checks order status, lists orders and cancels eligible orders after
human approval. The complete script below includes its data, tools, intents,
outcomes and direct `Agent(...)` initialization. No quickstart file or agent
factory is needed.

## Setup and run

Install DecisionAct v0.1.2 using [Installation](installation.md) and set
`TYPESAFE_API_KEY` as shown in the [quickstart](quickstart.md#1-set-the-api-key).
Save the code below as `my_order_agent.py`, then run:

```bash
python my_order_agent.py
```

Enter messages at `YOU>`. Each turn prints the reply and actual tool-call trace.
The script reads credentials from the environment and needs no `.env` helper.
Data resets when the process restarts; sessions use Python memory and a seven-message
conversation buffer. No database is created.

## Complete code

The tools, intents and outcomes match the
[repository order agent](https://github.com/Anil951/decisionact/blob/main/examples/order_agent.py).
The entry point below uses the environment directly and also prints tool traces.

```python
import os


from decisionact import Agent, Intent, Outcome, Param, tool
from decisionact.models import SystemOneModel
from decisionact.memory import ConversationBufferMemory
from decisionact.middleware import Approval, HumanInTheLoopMiddleware


ORDERS = {  # fake data
    "A1234": {"item": "iPhone 11 Pro", "status": "placed"},
    "B5678": {"item": "Samsung Galaxy Watch 6", "status": "dispatched"},
    "C9012": {"item": "Sony WH-1000XM5 Headphones", "status": "delivered"},
}

# ======================= TOOLS =======================
ORDER_ID = Param(desc="one uppercase letter followed by four digits, e.g. A1234",
                 pattern=r"\b[A-Z]\d{4}\b")

CANCEL_REASON = Param(
    desc="why the user cancels, as one of four categories: changed mind, delivery delay, "
         "wrong item ordered, other",
    options={"changed mind": "The user no longer wants the order or changed their mind.",
             "delivery delay": "The delivery is late or taking too long.",
             "wrong item ordered": "The user ordered the wrong item, size, colour or quantity.",
             "other": "The user gives any other reason."})


@tool(order_id=Param(desc=ORDER_ID.desc, pattern=ORDER_ID.pattern, optional=True))
def get_order(order_id: str = None) -> dict:
    """Look up an order's item and status (placed, dispatched, delivered or cancelled).
    With an order ID: returns that order. Without an order ID: returns all orders.
    Needed to answer status questions and to check an order before cancelling it."""
    if order_id is None:
        return {"orders": [{"order_id": o, **d} for o, d in ORDERS.items()]}
    if order_id not in ORDERS:
        return {"error": f"order {order_id} not found"}
    return {"order_id": order_id, **ORDERS[order_id]}


@tool(order_id=ORDER_ID, reason=CANCEL_REASON)
def cancel_order(order_id: str, reason: str) -> dict:
    """Cancel an order that is placed or dispatched (not delivered or already cancelled),
    with the reason for cancelling."""
    if order_id not in ORDERS:
        return {"error": f"order {order_id} not found"}
    order = ORDERS[order_id]
    if order["status"] in ("delivered", "cancelled"):
        return {"error": f"order {order_id} is {order['status']} and can't be cancelled",
                "item": order["item"], "status": order["status"]}
    order["status"] = "cancelled"
    return {"order_id": order_id, "item": order["item"], "status": "cancelled", "reason": reason}


# ======================= INTENTS =======================
INTENTS = {
    "order_status": Intent(
        desc="The user wants to know about an existing order or see their orders: where it is, "
             "its status, whether it has shipped or arrived, or a list of their orders. "
             "Examples: 'where is my order', 'status of A1234', 'has B5678 shipped?', "
             "'show my orders', 'track my package'. Also a reply that only gives an order ID "
             "after the agent asked which order to check. NOT cancelling (that is cancel_order).",
        context="Answer with exactly ONE get_order call, then stop: no further tool call is "
                "needed after get_order has returned. If the user's current message names an "
                "order ID, call get_order with it and the outcome is that order's status "
                "(placed, dispatched, delivered or cancelled_status), or not_found. If the "
                "current message names NO order ID, call get_order without one; it returns the "
                "list of all orders and the outcome is order_list. Never call get_order twice "
                "in the same turn.",
        tools=["get_order"],
        outcomes=["placed", "dispatched", "delivered", "cancelled_status", "not_found",
                  "order_list", "failed"]),
    "cancel_order": Intent(
        desc="The user wants to cancel or stop an order, or no longer wants it. "
             "Examples: 'cancel my order', 'cancel A1234', 'I don't want B5678 anymore', "
             "'stop my order, it's taking too long'. Also a reply that only gives an order ID "
             "and/or a reason after the agent asked which order to cancel or why. "
             "NOT refunds or returns of delivered items (that is out_of_scope).",
        context="Step 1: ALWAYS call get_order first, exactly once, even when the user names an "
                "order or picks one from a list the agent showed (e.g. 'the first one'). If the "
                "user's current message names or picks an order, call get_order for that order; "
                "otherwise call it without an order ID, which returns the list of all orders. "
                "Step 2: if get_order returned the LIST of all orders, stop: do NOT call "
                "cancel_order, the outcome is choose_order. If it returned one order that is "
                "delivered or cancelled, stop: the outcome is cancel_blocked. If it returned "
                "not found, stop: the outcome is not_found. If it returned one order that is "
                "placed or dispatched, call cancel_order for that same order ID. "
                "Never cancel an order the user did not name in this cancellation request.",
        tools=["get_order", "cancel_order"],
        outcomes=["cancelled", "cancel_blocked", "not_found", "choose_order", "failed"]),
    "greeting": Intent(
        desc="Greetings, thanks, goodbyes, small talk, or asking what the agent can do, with no "
             "order request in it. Examples: 'hi', 'good morning', 'how are you', 'thanks', "
             "'bye', 'what can you do?', 'are you a bot?'. If the message also asks about or "
             "cancels an order, it is NOT a greeting.",
        context="The user is greeting or making small talk. No tool is needed. Pick the category: "
                "opening the conversation, closing it, or asking what the agent can do.",
        tools=[],
        outcomes=["greet", "closing", "capabilities"]),
    "out_of_scope": Intent(
        desc="Any request that is neither checking an order's status nor cancelling an order. "
             "Examples: refunds, returns, complaints, changing the address, product questions, "
             "payments, weather, general questions.",
        context="The request is not about order status or cancellation. No tool is needed.",
        tools=[],
        outcomes=["out_of_scope"]),
}

# ======================= OUTCOMES =======================
OUTCOMES = {
    "greet": Outcome(
        desc="Opening or friendly small talk: hello, good morning, how are you, ok, cool.",
        reply="Hi! I can help you check an order's status or cancel an order. How can I help?"),
    "closing": Outcome(
        desc="Thanking or ending the conversation: thanks, bye, that's all, see you.",
        reply="You're welcome! Have a great day, and come back anytime you need help with "
              "your orders."),
    "capabilities": Outcome(
        desc="Asking what the agent can do or who it is: what can you do, help, are you a bot.",
        reply="I'm an order support assistant. I can show your orders, tell you an order's "
              "status, and cancel an order that hasn't been delivered yet."),
    "out_of_scope": Outcome(
        desc="The request is outside order status and cancellation.",
        reply="Sorry, I can only help with order status and cancellations."),
    "placed": Outcome(
        desc="get_order returned ONE order (with an order_id) whose status is placed.",
        reply="Your order {order_id} ({item}) is placed."),
    "dispatched": Outcome(
        desc="get_order returned ONE order (with an order_id) whose status is dispatched.",
        reply="Your order {order_id} ({item}) has been dispatched."),
    "delivered": Outcome(
        desc="get_order returned ONE order (with an order_id) whose status is delivered.",
        reply="Your order {order_id} ({item}) has been delivered."),
    "cancelled_status": Outcome(
        desc="get_order returned ONE order (with an order_id) whose status is cancelled.",
        reply="Your order {order_id} ({item}) was cancelled."),
    "not_found": Outcome(
        desc="A tool returned an error saying the order was not found.",
        reply="I couldn't find order {order_id}. Please check the ID."),
    "cancelled": Outcome(
        desc="cancel_order was called and returned status cancelled.",
        reply="Your order {order_id} ({item}) has been cancelled (reason: {reason})."),
    "cancel_blocked": Outcome(
        desc="get_order returned ONE order whose status is delivered or cancelled, so it can't "
             "be cancelled.",
        reply="Order {order_id} ({item}) can't be cancelled (status: {status})."),
    "order_list": Outcome(
        desc="get_order returned the LIST of all orders (an 'orders' list, no single order).",
        reply="Here are your orders:\n{orders}\nWhich order ID would you like to check?"),
    "choose_order": Outcome(
        desc="get_order returned the LIST of all orders (an 'orders' list, no single order), so "
             "the user must choose which order to cancel.",
        reply="Here are your orders:\n{orders}\nWhich order ID would you like to cancel, and why?"),
    # not offered to the model: chosen by the human-in-the-loop rule when a reviewer rejects
    "cancel_rejected": Outcome(
        desc="A reviewer rejected the cancellation.",
        reply="A reviewer declined to cancel order {order_id}. Reason: {rejection_reason}"),
    "failed": Outcome(
        desc="A tool returned an error that is not 'not found'.",
        reply="Something went wrong on our side. I'm handing you over to a human."),
}


if __name__ == "__main__":
    model = SystemOneModel(api_key=os.getenv("TYPESAFE_API_KEY"))
    approval = HumanInTheLoopMiddleware(approvals={
        "cancel_order": Approval(
            rejected_outcome="cancel_rejected",
            waiting="Cancelling order {order_id} needs approval. "
                    "Type /approve or /reject followed by a reason.",
        ),
    })
    agent = Agent(
        tools=[get_order, cancel_order],
        intents=INTENTS,
        outcomes=OUTCOMES,
        model=model,
        memory=ConversationBufferMemory(k=7),
        middleware=[approval],
    )

    # Try: "Where is A1234?" -> get_order("A1234") -> status placed.
    # Try: "Cancel A1234 because I changed my mind"
    #      -> get_order("A1234") -> wait for approval; cancellation has not run.
    # Then: "/approve" -> cancel_order("A1234", "changed mind") -> cancelled.
    print("Order support: try A1234, B5678 or C9012. Ctrl+C to quit.")
    while True:
        try:
            message = input("YOU> ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            break
        if message:
            result = agent.turn(message, session_id="order-demo")
            print("AGENT>", result.reply)
            print("TOOLS>", result.tool_calls)
```

## Sample messages, tool steps and outputs

These are expected paths when model decisions follow the configured rules.
Start with fresh demo data for each independent example; keep the same running
session for a sequence of follow-up messages. Arguments below show the values
passed to tools; `TOOLS>` prints the full inputs and outputs.

| Sample message | Expected tool steps | Expected reply or result |
| --- | --- | --- |
| `Where is A1234?` | 1. `get_order(order_id="A1234")` returns status `placed`. | `Your order A1234 (iPhone 11 Pro) is placed.` |
| `Has B5678 shipped?` | 1. `get_order(order_id="B5678")` returns status `dispatched`. | `Your order B5678 (Samsung Galaxy Watch 6) has been dispatched.` |
| `Show my orders` | 1. `get_order()` returns all three orders. | Lists A1234, B5678 and C9012, then asks which order ID to check. |
| `What is the status of Z9999?` | 1. `get_order(order_id="Z9999")` returns a not-found error. | `I couldn't find order Z9999. Please check the ID.` |
| `Cancel C9012 because I changed my mind` | 1. `get_order(order_id="C9012")` returns `delivered`. 2. Stop without cancellation. | `Order C9012 (Sony WH-1000XM5 Headphones) can't be cancelled (status: delivered).` |
| `Cancel my order because I changed my mind` | 1. `get_order()` lists orders. 2. Ask the user to choose; do not cancel. | Lists orders, then asks: `Which order ID would you like to cancel, and why?` |
| `Change my delivery address` | No tool; select the unsupported-request outcome. | `Sorry, I can only help with order status and cancellations.` |

### Cancellation with approval

This sequence shows lookup followed by an approved action. Use the same session:

| Step | User message | Tool execution | Expected reply |
| --- | --- | --- | --- |
| 1 | `Cancel A1234 because I changed my mind` | `get_order(order_id="A1234")` returns `placed`; middleware pauses the selected cancellation before execution. | `Cancelling order A1234 needs approval. Type /approve or /reject followed by a reason.` |
| 2 | `/approve` | `cancel_order(order_id="A1234", reason="changed mind")` changes the status to `cancelled`. | `Your order A1234 (iPhone 11 Pro) has been cancelled (reason: changed mind).` |
| 3 | `Status of A1234` | `get_order(order_id="A1234")` reads the changed status. | `Your order A1234 (iPhone 11 Pro) was cancelled.` |

To reject instead, send `/reject Keep the order` at step 2. No cancellation runs;
the reply is `A reviewer declined to cancel order A1234. Reason: Keep the order`.
Approval commands apply only while a call is waiting for review. A real
application must control who can approve a session.

### Choosing an order from a previous reply

1. Send `Show my orders`: `get_order()` lists A1234, B5678 and C9012.
2. Send `Cancel the first one because I changed my mind`: resolve A1234,
   call `get_order(order_id="A1234")` and wait for approval.
3. Send `/approve`: execute `cancel_order` for A1234 and return its cancellation reply.

## Missing inputs and limitations

- `Cancel A1234` looks up the order, then asks for a cancellation reason before
  requesting approval. Supply the reason in the same session.
- Low-confidence final outcome selection can return `rephrase` even after a tool
  succeeds. Inspect the trace and current order state before retrying cancellation.
- This intent deliberately performs one lookup per request. Repeated-call support
  does not remove application rules or add multi-intent execution.
- A missing-input pause retains partial inputs, but does not fully preserve an
  interrupted multi-operation request and its trace.

## Related concepts

See [tools](tools.md), [parameters](parameters.md), [intents](intents.md),
[outcomes](outcomes.md), [memory](memory-and-checkpoints.md) and
[middleware and approval](middleware-and-approval.md). The [calculator](calculator.md)
demonstrates repeated arithmetic calls, and the [flight desk](flight-desk-agent.md)
demonstrates lookup-before-action workflows with seven tools.
