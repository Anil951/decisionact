# Tools

## What a tool is

A tool is a Python function that performs an action or retrieves data. DecisionAct
uses its description to decide when it should run, resolves its inputs, and calls
the function. Your code performs the action and returns its result.

The function owns business validation and permissions. Model decisions choose
between the tools you allow; they do not replace the rules inside those tools.

## Define a tool

Use `@tool` to describe a function to the framework. This complete example runs
locally without a model or API key:

```python
from decisionact import Param, tool


@tool(
    left=Param(desc="The first number", pattern=r"-?\d+(?:\.\d+)?"),
    right=Param(desc="The second number", pattern=r"-?\d+(?:\.\d+)?"),
)
def add(left, right):
    """Add two numbers and return their total."""
    return {"total": float(left) + float(right)}


print(add("2", "3"))
```

Output:

```text
{'total': 5.0}
```

The function name, `add`, becomes its tool name. Its docstring becomes the tool
description used in model decisions. `@tool` returns the original function and
attaches its specification as `add.tool`; the function remains directly callable.

## Describe tool inputs

Give exactly one `Param` for every function argument. In the example, `left` and
`right` appear in both the decorator and function signature. Their descriptions
explain the inputs; their patterns help find number candidates.

Keep detailed input configuration on the [Parameters page](parameters.md):

- [Non-categorical inputs](parameters.md#non-categorical-inputs): names, numbers,
  and formatted codes, with or without a regex pattern.
- [Categorical inputs](parameters.md#categorical-inputs): a fixed set of choices
  declared with `options`.
- [Optional inputs](parameters.md#optional-inputs): `optional=True` together with
  a default in the Python signature.
- [Missing inputs](parameters.md#missing-inputs-and-follow-up-questions): questions
  and continuation when a required value cannot be resolved.

Values are not converted according to type annotations. The example converts
strings with `float()` inside the function. A regex helps extract a value; the
function still validates what it accepts.

## Register tools with an agent

Pass decorated functions to `Agent(tools=[...])`. Each intent lists the exact
names of the tools it may use. For the function above, use `tools=[add]` on the
agent and `tools=["add"]` on the calculation intent.

For an executable agent example, save the tool definition above in a Python file
and append this block. It reuses only that page's `add` function. Set
`TYPESAFE_API_KEY` in your environment before running the agent:

```python
import os
from decisionact import Agent, Intent, Outcome
from decisionact.models import SystemOneModel


if __name__ == "__main__":
    agent = Agent(
        tools=[add],
        intents={
            "calculate": Intent(
                desc="The user wants to add two numbers",
                context="Call add once; choose total on success and failed on error.",
                tools=["add"],
                outcomes=["total", "failed"],
            ),
            "other": Intent(desc="Requests unrelated to addition", outcomes=["help"]),
        },
        outcomes={
            "total": Outcome(desc="The tool returned a total", reply="The total is {total}."),
            "failed": Outcome(desc="The tool returned an error", reply="Could not add: {error}."),
            "help": Outcome(desc="The request is outside addition", reply="Ask me to add two numbers."),
        },
        model=SystemOneModel(api_key=os.getenv("TYPESAFE_API_KEY")),
    )
    result = agent.turn(message="Add 2 and 3", session_id="tools-demo")
    print(result.reply)
    print(result.tool_calls)
```

With successful model decisions, the reply is `The total is 5.0.` The tool trace
contains its name, resolved inputs, and output. Decisions are probabilistic and
can also lead to a rephrasing request or a missing-input question.

`Agent(...)` checks and stores the configuration; it does not run the tool.
Provider requests and selected tool calls happen during `turn()`. See
[Decision models](models.md) to use Jev or Cloudflare Clef.

## How a tool executes

During a turn, the framework:

1. Selects an [intent](intents.md) and considers only that intent's allowed tools.
2. Selects the next tool, or decides that no tool is needed.
3. Resolves the tool's [parameters](parameters.md), asking for missing values when needed.
4. Runs [middleware hooks](middleware-and-approval.md), which can pause execution.
5. Calls `Tool.run(**args)`, which invokes your function.
6. Records the result and decides whether to call another tool or choose an outcome.

After defining `add` above, you can call the same execution wrapper directly:

```python
result = add.tool.run(left="2", right="3")
print(result)
```

Output:

```text
{'total': 5.0}
```

This direct wrapper call does not select an intent, resolve values from a user
message, or run agent middleware. Those steps belong to `Agent.turn()`.

## Return values and replies

Return a dictionary with clear top-level fields when the result should fill a
reply template. The example returns `{"total": 5.0}`. The `total` outcome above uses
`"The total is {total}."`, producing:

```text
The total is 5.0.
```

Resolved tool inputs and dictionary output fields are available to templates.
Later calls overwrite earlier values with the same key. List values are rendered
as bullet lines, and missing template keys become empty strings.

A function can return other Python values, but only dictionary output fields are
merged into the named template values. The result itself still appears in the
tool trace. See [Outcomes](outcomes.md) for reply behavior.

## Errors and validation

A direct call such as `add("hello", "3")` raises the ordinary Python conversion
exception. The framework wrapper catches ordinary function exceptions and returns
`{"error": str(exception)}` instead.

After defining `add`, this local check demonstrates that behavior without an API
request:

```python
result = add.tool.run(left="hello", right="3")
print("error" in result)
```

Output:

```text
True
```

You can also return an explicit error dictionary for a business failure. The
model evaluates the tool output; your configured intents and outcomes describe
how to respond. An error dictionary does not itself select an outcome.

Tool exception wrapping does not catch provider failures or all other agent
errors. Model availability and request errors can still propagate to the caller.
Enforce validation and permissions before performing an external action.

## Behavior and limitations

- A tool needs a nonempty docstring.
- Each function argument needs exactly one matching parameter declaration.
- Every parameter needs a description; nonempty `pattern` and `options` cannot be combined.
- Optional inputs require both `optional=True` and a Python default.
- Type annotations do not convert input values. Convert and validate inside the function.
- Agent tool names and intent tool references must match exactly.
- Tool calls are synchronous. The default tool-loop limit is six calls per turn,
  configurable with `Agent(max_calls=...)`.
- Approval can stop a selected function before it runs. Direct function or
  `Tool.run()` calls do not apply that middleware.
- A later provider failure does not undo an earlier tool effect. Use idempotent
  operations when repeated execution could otherwise create duplicate actions.

## Related pages and API

- [Parameters](parameters.md): input descriptions, patterns, categories, and defaults.
- [Intents](intents.md): which tools are allowed for each request.
- [Outcomes](outcomes.md): result fields and reply templates.
- [Middleware and approval](middleware-and-approval.md): hooks before execution.
- [tool and Tool API reference](api-reference.md#tools-inputs-intents-and-outcomes): signatures and validation.
- [Execution flow](execution-flow.md): the full call sequence.
