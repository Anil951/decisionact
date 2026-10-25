# Calculator

The v0.1.2 calculator example demonstrates several sequential tool calls within
one intent, including repeating a tool and selecting earlier results as later
inputs. It defines `add(a, b)`, `subtract(a, b)`, `multiply(a, b)` and `divide(a, b)`.

[View calculator.py](https://github.com/Anil951/decisionact/blob/main/examples/calculator.py).
Its comments include the query types used during development, their intended
tool traces and replies, and cases that need clarification or error handling.
The previous experimental filename was `repeated_add.py`.

## Complete code

Install the local v0.1.2 package as described in [Installation](installation.md)
and set `TYPESAFE_API_KEY` in your terminal as shown in the
[quickstart](quickstart.md#1-set-the-api-key). Save this complete file as
`my_calculator.py`. It defines the tools, intents and outcomes, then constructs
`Agent(...)` directly. It does not import another example or require `python-dotenv`.

```python
import os

from decisionact import Agent, Intent, Outcome, Param, tool
from decisionact.models import SystemOneModel

NUMBER = r"-?(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][+-]?\d+)?"


@tool(
    a=Param(desc="The first operand of the requested addition", pattern=NUMBER),
    b=Param(desc="The second operand of that addition", pattern=NUMBER),
)
def add(a, b):
    """Add two numbers: a + b."""
    value = float(a) + float(b)
    return {"result": int(value) if value.is_integer() else value}


@tool(
    a=Param(desc="The number to subtract from", pattern=NUMBER),
    b=Param(desc="The number to subtract from a", pattern=NUMBER),
)
def subtract(a, b):
    """Subtract b from a: a - b."""
    value = float(a) - float(b)
    return {"result": int(value) if value.is_integer() else value}


@tool(
    a=Param(desc="The first factor of the requested multiplication", pattern=NUMBER),
    b=Param(desc="The second factor of that multiplication", pattern=NUMBER),
)
def multiply(a, b):
    """Multiply two numbers: a * b."""
    value = float(a) * float(b)
    return {"result": int(value) if value.is_integer() else value}


@tool(
    a=Param(desc="The number being divided", pattern=NUMBER),
    b=Param(desc="The number to divide a by", pattern=NUMBER),
)
def divide(a, b):
    """Divide a by b: a / b."""
    divisor = float(b)
    if divisor == 0:
        raise ValueError("Cannot divide by zero.")
    value = float(a) / divisor
    return {"result": int(value) if value.is_integer() else value}


INTENTS = {
    "calculate": Intent(
        desc="Perform requested additions, subtractions, multiplications and divisions",
        context=(
            "Four arithmetic tools are available: "
            "add(a, b) returns a + b; call for addition. "
            "subtract(a, b) returns a - b; call to subtract b from a. "
            "multiply(a, b) returns a * b; call for multiplication. "
            "divide(a, b) returns a / b; call to divide a by b. "
            "All tools take two numeric operands, a and b."
        ),
        tools=["add", "subtract", "multiply", "divide"],
        outcomes=["done", "failed"],
    ),
}

OUTCOMES = {
    "done": Outcome(
        desc="All requested arithmetic operations succeeded",
        reply="Result: {result}",
    ),
    "failed": Outcome(
        desc="An arithmetic operation failed",
        reply="Calculation failed: {error}",
    ),
}


if __name__ == "__main__":
    model = SystemOneModel(api_key=os.getenv("TYPESAFE_API_KEY"))
    agent = Agent(
        tools=[add, subtract, multiply, divide],
        intents=INTENTS,
        outcomes=OUTCOMES,
        model=model,
    )
    # Sample messages: replace message below to try one.
    # These are expected successful traces; live model decisions can vary.
    #
    # "Add 4+5 and add 6+7"
    # Calls: add(4, 5)=9 -> add(6, 7)=13. Reply: "Result: 13".
    #
    # "Add 4+5, then add the result to 7"
    # Calls: add(4, 5)=9 -> add(9, 7)=16. Reply: "Result: 16".
    #
    # "Divide 8 by 2 twice, as two separate independent calculations"
    # Calls: divide(8, 2)=4 -> divide(8, 2)=4. Reply: "Result: 4".
    #
    # "Divide 5 by 2, multiply the result by 4, subtract 3 from that result,
    # then add 1 to the result"
    # Calls: divide(5, 2)=2.5 -> multiply(2.5, 4)=10
    #        -> subtract(10, 3)=7 -> add(7, 1)=8. Reply: "Result: 8".
    result = agent.turn(
        message="Add 4+5 and add 6+7",
        session_id="calculator-demo",
    )
    print(result.reply)
    print(result.tool_calls)
```

## Run the example

```bash
python my_calculator.py
```

With successful model decisions, this prints `Result: 13`, followed by the two
tool calls and their inputs and outputs. Change `message` to try the other queries
below. Provider requests use your configured account; importing the file does
not start a request.

The repository script is also available from a checkout with the `examples` extra:

```bash
python -m examples.calculator "Add 4+5 and add 6+7"
```

That command prints JSON containing the message, outcome, reply, calls and
decisions. Without a message, the repository script runs the mixed chain below.

## Sample messages, tool steps and outputs

These are expected successful paths; live model decisions can vary. Change
`message` in the complete script to try each query. The reply shows the last
result, and `result.tool_calls` contains every call's inputs and output.

| Sample message | Expected tool steps | Expected reply |
| --- | --- | --- |
| `Add 4+5 and add 6+7` | 1. `add(4, 5)` returns `9`. 2. `add(6, 7)` returns `13`. | `Result: 13` |
| `Add 4+5, then add the result to 7` | 1. `add(4, 5)` returns `9`. 2. `add(9, 7)` returns `16`. | `Result: 16` |
| `Divide 8 by 2 twice, as two separate independent calculations` | 1. `divide(8, 2)` returns `4`. 2. `divide(8, 2)` returns `4` again. | `Result: 4` |
| `Divide 5 by 2, multiply the result by 4, subtract 3 from that result, then add 1 to the result` | 1. `divide(5, 2)` returns `2.5`. 2. `multiply(2.5, 4)` returns `10`. 3. `subtract(10, 3)` returns `7`. 4. `add(7, 1)` returns `8`. | `Result: 8` |

## Repeating a tool

For `Add 4+5 and add 6+7`, the intended execution is:

| Step | What happens |
| --- | --- |
| 1 | Select the `calculate` intent, then the permitted `add` tool. |
| 2 | Resolve `a=4` and `b=5` for this invocation; execute `add(4, 5)` and record `9`. |
| 3 | Inspect the request and completed call; decide whether another tool is needed. |
| 4 | Select `add` again with a fresh input cache. Earlier call details remain visible. |
| 5 | Resolve `a=6` and `b=7`; execute `add(6, 7)` and record `13`. |
| 6 | Decide the requested calculations are complete and select `done`. |

The reply is `Result: 13`. Both `9` and `13` remain in `result.tool_calls`.
Independent identical calculations, such as `Divide 8 by 2 twice, as two separate
independent calculations`, should execute `divide(8, 2)` twice. Repeated values
are allowed; they are not automatically consumed or banned after their first use.

## Using earlier results

For `Add 4+5, then add the result to 7`:

1. `add(4, 5)` returns `{"result": 9}`.
2. The current-turn trace identifies that output's tool, arguments and result.
3. Parameter choices can include `9`, labelled with its source call and field,
   alongside numbers extracted from the message.
4. The second invocation selects `9` and `7`, executes `add(9, 7)` and returns `16`.
5. The final template renders `Result: 16`.

The model selects from supplied choices; it does not generate unrestricted
arguments or compute `9` itself. The Python tool produces the value. Eligible
output scalars can come from nested dictionaries or lists; regex constraints
still apply, and categorical inputs keep their declared options.

## Mixing tools

```text
Divide 5 by 2, multiply the result by 4, subtract 3 from that result,
then add 1 to the result.
```

| Call | Output |
| --- | --- |
| `divide(5, 2)` | `2.5` |
| `multiply(2.5, 4)` | `10` |
| `subtract(10, 3)` | `7` |
| `add(7, 1)` | `8` |

The intended reply is `Result: 8`. Negative numbers, decimals, zero and scientific
notation are accepted by the example's numeric pattern; tools convert input text
to floats. Floating-point arithmetic has the usual precision limits.

## Inspecting calls and changing limits

To use smaller allowances, replace the `Agent(...)` constructor in the complete
script above with:

```python
agent = Agent(
    tools=[add, subtract, multiply, divide],
    intents=INTENTS,
    outcomes=OUTCOMES,
    model=model,
    max_calls=2,
    max_call_limit=8,
)
```

Then use this turn and inspection code inside the same `__main__` block:

```python
result = agent.turn(
    "First add 4 and 5. Next subtract 3 from 10. Finally multiply 2 by 6."
)
print(result.reply)
for call in result.tool_calls:
    print(call["tool"], call["inputs"], call["output"])
if result.outcome == "limit_reached":
    print(result.limit_reason)
```

After two executions, a Noul can grant another allowance of two. If granted, the
third calculation runs and the reply is `Result: 12`. The total count and earlier
calls are retained. Defaults are an allowance of six and a hard cap of 24.
An extension denial or further work at the hard cap returns `limit_reached`
with an unfinished-work reply, rather than claiming completion. See
[tool-call limits](api-reference.md#tool-call-limit).

## Missing values, errors and reply scope

| Query | Intended handling |
| --- | --- |
| `Add 4+5, then add 4+7` | Execute both independent additions; reuse `4` and finish with `11`. Do not invent a third addition. |
| `Add 4+5, then multiply the result by an unknown number` | Calculate `9`, then ask for the multiplier before multiplication. |
| `Add 4+5 and multiply 2 by 6, then divide one of those results by 3` | Calculate `9` and `12`, then ask which result is meant. |
| `Divide 5 by 0` | Call the tool; report its error or ask for a corrected divisor through input repair. |
| `Add 4+5, divide that result by 0, then multiply the result by 3` | Record the addition and division error; do not use an unsuccessful division as a valid result. |

These are expected behaviors, not guarantees for every live run. Shared values
and ambiguous references can still lead to incorrect choices or extra calls.
A low-confidence input Choice gets one recheck with unchanged choices and
threshold, then asks for the value if still uncertain. Other low-confidence
decisions can return `rephrase`, even after a tool has run.

The example defines only `done` and `failed`. Framework statuses such as `asking`,
`rephrase` and `limit_reached` require no additional outcome declarations. Its
`done` template shows the last `result`; it does not aggregate independent answers.
Use the ordered trace when your interface needs every calculation.

A paused call retains its resolved inputs. Preserving the original multi-operation
request and full execution trace across clarification turns is not fully supported;
successful single-call correction does not guarantee a whole interrupted chain
will resume. This feature remains a single-agent, single-intent tool loop.

See [execution flow](execution-flow.md), [parameters](parameters.md),
[outcomes](outcomes.md) and [API reference](api-reference.md).
