# Parameters

## What a parameter is

A parameter describes one input to a tool. DecisionAct resolves that input from
the conversation before it calls your Python function.

There are two kinds of input in the current implementation:

- **Non-categorical:** a value such as a name, number, or code. Use a description
  and, optionally, a regex `pattern`.
- **Categorical:** one of a fixed set of named values. Declare these with `options`.

Both kinds can be optional. An integer is not a separate `Param` type: converting
an extracted value to `int` or `float` is the tool's responsibility.

## Configuration

```python
from decisionact import Param

name = Param(desc="The person's name")
```

| Field | Default | Purpose |
| --- | --- | --- |
| `desc` | Required | Describes what the input means. |
| `pattern` | `None` | Regex used to find candidate text values. |
| `options` | `None` | Dictionary of category keys and their meanings. |
| `optional` | `False` | Allows omission when the current message does not supply the input. |

Give exactly one `Param` for every tool argument. Use `pattern` or `options`,
not both.

The examples below are independent, complete snippets. Their direct function calls
run locally without a model or API key. Parameter extraction happens when the
function is registered with an agent and selected during `agent.turn(...)`;
a direct Python call simply uses the arguments you pass.

## Non-categorical inputs

Names, numbers, and formatted codes are values extracted from text rather than
chosen from a fixed set of categories.

### Name: ordinary text

Use a description when the value has no fixed format or list of categories:

```python
from decisionact import Param, tool


@tool(name=Param(desc="The person's name"))
def say_hello(name):
    """Return a greeting for a person."""
    return {"message": f"Hello, {name}!"}


print(say_hello("Sam"))
```

Output:

```text
{'message': 'Hello, Sam!'}
```

During a turn, the engine considers text-span candidates and asks the decision
model which span is the name. A description does not mean unrestricted long-text
extraction: candidate length and count are bounded by the agent's settings.

### Number: integer conversion

Use a numeric pattern to find a number, then convert it inside the function:

```python
from decisionact import Param, tool


@tool(number=Param(desc="The whole number to double", pattern=r"-?\d+"))
def double_number(number):
    """Double an integer and return the result."""
    value = int(number)
    return {"result": value * 2}


print(double_number("4"))
```

Output:

```text
{'result': 8}
```

The extracted text is still a string such as `"4"`. Writing `number: int` in the
function signature would not convert it automatically. Use `int(number)` for
integer values or `float(number)` for decimal values, with a suitable pattern
and validation for the format your tool accepts.

If conversion fails, a direct call raises the normal Python exception. During
framework execution, `Tool.run()` converts an ordinary function exception into
an output dictionary containing `error`.

### Code: regex pattern matching

A pattern can describe text such as one uppercase letter followed by two digits:

```python
import re
from decisionact import Param, tool


@tool(code=Param(desc="One uppercase letter and two digits", pattern=r"\b[A-Z]\d{2}\b"))
def show_code(code):
    """Validate a short code and return it."""
    if re.fullmatch(r"[A-Z]\d{2}", code) is None:
        return {"error": "Use a code such as A12"}
    return {"code": code}


print(show_code("A12"))
```

Output:

```text
{'code': 'A12'}
```

The regex finds candidate values; the tool validates the final input. If there is
one eligible match in the current message, the engine can use it directly. If
there are multiple matches, it asks the model to choose.

A regex is not a strict validation boundary. If it finds no matches, the engine
can fall back to other text spans. Keep format and business validation in the tool.

## Categorical inputs

Use `options` when the input must be one of a known set of categories. This example
lets the user choose red or blue:

```python
from decisionact import Param, tool


@tool(color=Param(
    desc="The requested color",
    options={"red": "The user wants red", "blue": "The user wants blue"},
))
def choose_color(color):
    """Return the chosen supported color."""
    if color not in {"red", "blue"}:
        return {"error": "Choose red or blue"}
    return {"color": color}


print(choose_color("blue"))
```

Output:

```text
{'color': 'blue'}
```

During a turn, the model chooses an `options` key, such as `red` or `blue`, using
its description. The key is passed to the function. If it selects no category or
is below the confidence threshold, the engine can ask which color the user wants.
Direct function calls do not run category selection, so the example also validates
its input inside the function.

## Optional inputs

Set `optional=True` and provide a default in the function signature:

```python
from decisionact import Param, tool


@tool(name=Param(desc="The person's name", optional=True))
def greet(name="friend"):
    """Greet a person, or use a default name."""
    return {"message": f"Hello, {name}!"}


print(greet())
print(greet("Sam"))
```

Output:

```text
{'message': 'Hello, friend!'}
{'message': 'Hello, Sam!'}
```

During a turn, the engine first asks whether the current message supplies or
refers to this optional value. If not, it omits the argument and the Python
default takes effect. If the user supplies it, the engine resolves it normally.
The same setting works with a categorical `options` parameter.

A Python default by itself does not make an input optional to the framework.
Declare `optional=True` as well. Conversely, an optional declaration without a
Python default is rejected when the tool is decorated.

## Missing inputs and follow-up questions

If a required input cannot be resolved, the agent can return a question with
outcome `asking` and save a paused tool call. Supply the answer through another
`agent.turn(message, session_id=...)` using the same session ID.

The engine checks whether the new message answers the pending question before
continuing that call. If it starts a different request, the paused call can be
dropped. Questions and rejected-value retries are limited by the agent settings.

## Behavior and limitations

- A description is required for each parameter.
- Type annotations do not convert extracted values.
- Do not combine a nonempty `pattern` with nonempty `options` on the same input.
- By default, text-span candidates contain up to three words, with at most 40
  candidates considered. Configure `Agent.window` and `Agent.max_candidates`
  through the corresponding constructor arguments for your use case.
- Required non-categorical inputs can consider a previously successful value.
  Optional inputs first depend on whether the current message supplies or refers
  to a value; they are not silently filled from that previous-value fallback.
- Optional-input detection sees at most four previous messages when memory is enabled.
- Extraction and category decisions do not replace tool validation or permissions.

## Related API links

See [Param and @tool](api-reference.md#tools-inputs-intents-and-outcomes),
[agent limits](api-reference.md#agent), [tools](tools.md), and
[input resolution](execution-flow.md#resolving-an-input).
