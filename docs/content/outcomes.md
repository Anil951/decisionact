# Outcomes

## What an outcome is

An outcome describes how a turn can end and the predefined reply for that ending.
An [intent](intents.md) describes what the user wants; its outcomes describe the
possible results. For example, checking a number can end with a positive-number,
non-positive-number, or error outcome.

The model chooses among the selected intent's allowed outcomes using their
descriptions and the current state. The framework then fills the chosen reply
template. It does not ask the model to write a new free-form answer. Declaring an
outcome does not itself execute a tool or send a response.

## Configuration

Import `Outcome` from `decisionact` and register outcomes in a dictionary. Its
key, such as `"total"`, is the outcome name:

| Field | Purpose |
| --- | --- |
| `desc` | Explains when the model should choose this ending. |
| `reply` | The predefined reply template, filled after the ending is selected. |

Both constructor arguments are required. Use explicit `desc=` and `reply=` so the
description and user-facing text are easy to distinguish.

Pass this dictionary to `Agent(outcomes=...)` and reference its keys in
`Intent(outcomes=[...])`. Each intent needs at least one outcome. Different intents
may share the same registered outcome.

Agent construction checks that registered values are `Outcome` objects and that
intent outcome names exist. Wrong object types raise `TypeError`; missing or
unknown intent outcome references raise `ValueError`. Template data and all
format-string behavior are not validated in advance.

## Examples

### Define an outcome

This complete declaration example runs locally without a model or API key:

```python
from decisionact import Outcome

outcomes = {
    "total": Outcome(
        desc="The calculation returned a total",
        reply="The total is {total}.",
    ),
    "failed": Outcome(
        desc="The calculation returned an error",
        reply="Could not calculate: {error}.",
    ),
}

print(outcomes["total"].reply)
```

Output:

```text
The total is {total}.
```

The declaration stores the template. It is rendered during a turn, not when the
`Outcome` is created.

### Fill templates from tool results

If a tool returns this dictionary during a turn:

```python
{"total": 5.0}
```

the `total` outcome above renders:

```text
The total is 5.0.
```

Template values come from resolved tool inputs and top-level dictionary output
fields for the current turn. In one call, an output field overrides an input with
the same name. Later calls override earlier values with the same name. Memory
history is not automatically merged into these template fields.

A non-dictionary tool result is still a tool result, but does not contribute named
output fields to the template. Return a dictionary when the reply needs those fields.

### Lists and missing values

List-valued fields become bullet lines. For example, a tool output of:

```python
{"items": ["Apple", "Banana"]}
```

with `reply="Available items:\n{items}"` produces:

```text
Available items:
- Apple
- Banana
```

For a list containing dictionaries, each bullet uses the dictionary's first value
followed by its other values in parentheses, in dictionary iteration order.

A missing simple placeholder such as `{name}` becomes an empty string. Format
specifications still need compatible values: `{total:.2f}` needs a numeric total.
Invalid specifications, malformed braces, or unsupported nested lookups can raise
normal formatting or lookup errors. Use `{{` and `}}` for literal braces.

## Using outcomes in an agent

This complete, independent example has several outcomes for checking a number.
It prints the selected intent, outcome, and reply for two inputs. Set
`TYPESAFE_API_KEY` in your environment before running it with Jev:

```python
import os
from decisionact import Agent, Intent, Outcome, Param, tool
from decisionact.models import SystemOneModel


@tool(number=Param(desc="The integer to check", pattern=r"-?\d+"))
def check_number(number):
    """Return an integer and whether it is positive or non-positive."""
    value = int(number)
    return {
        "number": value,
        "kind": "positive" if value > 0 else "non_positive",
    }


if __name__ == "__main__":
    agent = Agent(
        tools=[check_number],
        intents={
            "check": Intent(
                desc="The user wants to check whether an integer is positive",
                context="Call check_number once. Use its kind as the outcome, or failed on error.",
                tools=["check_number"],
                outcomes=["positive", "non_positive", "failed"],
            ),
            "other": Intent(
                desc="Requests unrelated to checking an integer",
                context="Offer help for this number-checking demo.",
                outcomes=["help"],
            ),
        },
        outcomes={
            "positive": Outcome(
                desc="The tool returned kind positive",
                reply="{number} is positive.",
            ),
            "non_positive": Outcome(
                desc="The tool returned kind non_positive",
                reply="{number} is zero or negative.",
            ),
            "failed": Outcome(
                desc="The tool returned an error",
                reply="Could not check the number: {error}.",
            ),
            "help": Outcome(
                desc="The request is outside number checking",
                reply="Ask me to check an integer.",
            ),
        },
        model=SystemOneModel(api_key=os.getenv("TYPESAFE_API_KEY")),
    )
    for index, message in enumerate(["Check number 4", "Check number -2"], start=1):
        result = agent.turn(message=message, session_id=f"outcome-demo-{index}")
        print(f"Input: {message}")
        print(f"Intent: {result.intent}")
        print(f"Outcome: {result.outcome}")
        print(f"Reply: {result.reply}")
        print()
```

One possible run, when decisions follow the tool results:

```text
Input: Check number 4
Intent: check
Outcome: positive
Reply: 4 is positive.

Input: Check number -2
Intent: check
Outcome: non_positive
Reply: -2 is zero or negative.
```

The same intent leads to different outcomes, and `{number}` is filled from the
tool result. The tool's `kind` field informs the model; it is not a direct outcome
assignment. Decisions remain probabilistic, and an error dictionary does not
by itself select the `failed` outcome.

`result.outcome` holds the chosen outcome key and `result.reply` holds the rendered
text. Outcome Choice records appear in `result.decisions`, either in after-tool
evaluation or in a separate final outcome decision.

The engine uses an accepted outcome from tool evaluation when available.
Otherwise, it selects a sole allowed outcome without an additional final Choice,
or asks the model to choose among multiple allowed outcomes. After-tool evaluation
can still include an outcome Choice even when only one ending is allowed. Model
Choices use `min_conf`, which defaults to `0.6`; low confidence can produce a
rephrasing request instead of an ordinary outcome reply.

Handled turns can also return framework status values rather than a registered
outcome key:

| `result.outcome` | Meaning |
| --- | --- |
| `rephrase` | A decision was below the confidence threshold. |
| `asking` | A tool input needs a follow-up answer. |
| `stopped` | The same paused input exceeded the question limit. |
| `awaiting_approval` | Middleware interrupted execution, such as a tool waiting for review. |

These statuses do not need declarations in your outcomes dictionary. Inspect
`result.paused` or `result.pending_approval` when handling the corresponding wait.

For human approval, rejection uses the rule's registered rejection outcome
directly, without a model outcome choice. It need not appear in `Intent.outcomes`.
Its template can use the pending inputs, previous tool facts, and
`{rejection_reason}`. See [middleware and approval](middleware-and-approval.md).

Provider exceptions and unhandled rendering errors can propagate without returning
a normal `TurnResult`. Outcomes do not undo tool effects, and an exception before
the normal save step does not create an automatic recovery checkpoint.

## Related pages and API

- [Intents](intents.md): allowed endings for each request category.
- [Tools](tools.md): returned data and tool errors.
- [Parameters](parameters.md): resolved inputs available to templates.
- [Decision models](models.md): Choice confidence and provider errors.
- [Middleware and approval](middleware-and-approval.md): review and rejection outcomes.
- [Outcome API reference](api-reference.md#tools-inputs-intents-and-outcomes): constructor signatures.
- [TurnResult](api-reference.md#turnresult): outcome, reply, and continuation fields.
- [Execution flow](execution-flow.md): when outcome selection and rendering happen.
