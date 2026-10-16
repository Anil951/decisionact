# Building agents

[Documentation](README.md) / Building agents

Start with `my_order_agent.py` from the [quickstart](quickstart.md). This guide
explains its pieces and extends it with cancellation.

## Choose the model

Jev uses the TypeSafe SDK:

```python
import os
from decisionact.models import SystemOneModel

model = SystemOneModel(
    api_key=os.getenv("TYPESAFE_API_KEY"),
    model="jev-latest",
    min_conf=0.6,
    timeout=30.0,
)
```

To use Clef instead, replace that initialization with:

```python
import os
from decisionact.models import CloudflareModel

model = CloudflareModel(
    api_token=os.getenv("CLOUDFLARE_API_TOKEN"),
    account_id=os.getenv("CLOUDFLARE_ACCOUNT_ID"),
    model="clef",
    min_conf=0.6,
    timeout=30.0,
)
```

Both produce a `DecisionModel` accepted by `Agent`. Clef's model name appears in
its Workers AI URL. Credentials, access, and model availability are checked by the
provider when a request is made; creating an adapter is not a live connectivity test.

`min_conf` is the lowest trusted Choice confidence. Noul answers use their own
yes/no threshold of `0.5` in the engine. Tune confidence against representative
requests for your chosen model, rather than assuming providers are calibrated alike.

Missing keys or model names raise `DecisionModelNotFound` locally. Mapped provider
authentication, permission, and model-not-found responses also raise it. Missing
Cloudflare account IDs raise `ValueError`. Other request failures can raise
`DecisionModelError`. These exceptions propagate; the example agents do not add
model-error handlers.

## Define tools

The quickstart's `get_order` remains a normal callable:

```python
from my_order_agent import get_order

print(get_order("A1234"))
```

This direct call needs no model. During a turn, DecisionAct calls the associated
`Tool.run(**args)`, which calls your function. That wrapper converts ordinary
function exceptions into `{"error": "..."}` tool output. A direct Python call
still raises normal Python exceptions, including `TypeError` for missing arguments.

Give every tool a docstring and exactly one `Param` for every function argument.
Input values are not automatically converted according to type annotations:
convert numbers and validate business rules inside the function.

## Describe parameters

Use `pattern` to find candidate text with a regex, or `options` for a category.
Do not specify both on the same parameter.

An optional parameter also needs a Python default. This standalone illustration
reuses the quickstart data but does not change the running agent:

```python
from decisionact import Param, tool
from my_order_agent import ORDERS

@tool(order_id=Param("Optional order ID", pattern=r"\b[A-Z]\d{4}\b", optional=True))
def list_or_get_order(order_id=None):
    """Return all orders, or one order when an ID is supplied."""
    if order_id is None:
        return {"orders": [{"order_id": key, **value} for key, value in ORDERS.items()]}
    return {"order_id": order_id, **ORDERS.get(order_id, {"error": "Order not found"})}
```

The engine first asks whether the current message supplies an optional input.
If not, it omits that argument so the function's default takes effect.

A regex is an extraction hint, not a complete validator. If no match is found,
the engine can ask the model to select from text-span candidates. A missing or
uncertain value leads to a follow-up question. Validate the final value in the tool.

## Add cancellation to the order agent

Insert the following block into `my_order_agent.py` **above** its `__main__` guard.
It uses the imports, `ORDERS`, `ORDER_ID`, `INTENTS`, and `OUTCOMES` already defined there:

```python
@tool(
    order_id=ORDER_ID,
    reason=Param(
        "Why the customer wants to cancel",
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
    "Cancel an order",
    context="Call cancel_order once. End with cancelled on success or cancel_failed on error.",
    tools=["cancel_order"],
    outcomes=["cancelled", "cancel_failed"],
)
INTENTS["other"] = Intent(
    "Any request unrelated to checking or cancelling orders", outcomes=["help"]
)
OUTCOMES["cancelled"] = Outcome(
    "cancel_order returned status cancelled",
    "Order {order_id} was cancelled: {reason}.",
)
OUTCOMES["cancel_failed"] = Outcome(
    "cancel_order returned an error",
    "Could not cancel order {order_id}: {error}.",
)
OUTCOMES["help"] = Outcome(
    "The request is outside order support", "I can check or cancel orders."
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
result = agent.turn("Cancel A1234 because I changed my mind", session_id="customer-1")
print(result.reply)
```

With successful model decisions, the reply is:

```text
Order A1234 was cancelled: changed mind.
```

This version executes cancellation immediately. The next guide adds approval.

## Intents, outcomes, and templates

Intent `tools` entries must match decorated function names, and `outcomes` entries
must match keys in the outcomes dictionary. An intent needs at least one outcome;
it can have no tools, such as the `other` intent above.

`context` guides subsequent model decisions. It is not executable Python or a
business-rule validator; keep eligibility rules inside your tools.

Templates can use tool input names and top-level output keys. Later tool results
overwrite earlier values with the same key. Lists are rendered as bullet lines.
Missing template keys render as empty strings, so check the data your tools return.

## Common mistakes

| Mistake | Correction |
| --- | --- |
| No tool docstring | Describe what the function does and what it returns. |
| A function argument has no `Param` | Provide a matching declaration in `@tool`. |
| Optional input has no default | Add a default such as `order_id=None`. |
| Expecting `int` annotations to convert input | Convert and validate values inside the tool. |
| Unknown tool or outcome name | Use the registered names exactly. |
| No out-of-scope intent | Add an explicit fallback category; the model otherwise chooses among the provided intents. |

Next: [Memory and approval](memory-and-approval.md).
