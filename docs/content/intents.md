# Intents

## What an intent is

An intent describes a kind of user request, the tools it may use, and the outcomes
it can end with. For example, a greeting can reply without a tool, while a
calculation can call a function and use its result.

For a new request, the decision model chooses among your registered intent names
using their descriptions and the conversation state. v0.1.1 handles one intent per
message. That intent may involve several tool calls; multi-intent and multi-agent
workflows are planned for future versions.

Write distinct descriptions so the available categories are easy to distinguish.
Overlapping descriptions can make model selection ambiguous.

## Configuration

Import `Intent` from `decisionact`. The dictionary key, such as `"greeting"`, is
the intent's name. The object describes its behavior:

| Field | Default | Purpose |
| --- | --- | --- |
| `desc` | Required | Describes the requests that belong to this intent. |
| `context` | `""` | Guides decisions after the intent has been selected. |
| `tools` | `[]` | Names of registered tool functions this intent may use. |
| `outcomes` | `[]` | Names of possible endings; at least one is required when registered with an agent. |

`context` is added to subsequent tool, input, and outcome decisions. It guides the
model; it is not executable logic or a replacement for validation and permissions
inside your functions. Initial intent selection uses `desc`, not a rule expressed
in `context`.

When you construct `Agent(...)`, it checks that:

- Each entry in the intents dictionary is an `Intent` object.
- Every intent has at least one outcome.
- Its tool names match functions registered in the agent's tools list.
- Its outcome names exist in the agent's outcomes dictionary.

Wrong object types raise `TypeError`; missing outcomes and unknown tool or outcome
references raise `ValueError`. Each intent gets independent default lists.

Different intents can reference the same registered tools and outcomes. These
definitions do not have to belong exclusively to one intent.

For [human approval](middleware-and-approval.md), a rejection outcome must exist
in the agent's outcomes dictionary, but does not have to appear in the intent's
ordinary `outcomes` list. The approval rule selects that rejection ending directly.

## Examples

### A greeting without tools

This complete local declaration example needs no model or API key:

```python
from decisionact import Intent

intents = {
    "greeting": Intent(desc="The user says hello", outcomes=["welcome"]),
}

print(intents["greeting"].tools)
print(intents["greeting"].outcomes)
```

Output:

```text
[]
['welcome']
```

An intent with no tools skips the tool loop. If it has only one allowed outcome,
that ending can be selected without an additional outcome-model call. Selecting
the intent for a new request still uses the decision model.

### A calculation that allows a tool

This separate declaration describes a tool-backed intent:

```python
from decisionact import Intent

calculate = Intent(
    desc="The user wants to add two numbers",
    context="Call add once; choose total on success or failed on an error.",
    tools=["add"],
    outcomes=["total", "failed"],
)

print(calculate.tools)
```

Output:

```text
['add']
```

Before using this intent in an agent, register a decorated function named `add`
and define `total` and `failed` outcomes. See [Tools](tools.md) for a complete
addition example and [Parameters](parameters.md) for its input declarations.

The tools list permits those calls; it does not force every listed function to
run. The engine can choose another allowed tool or decide no tool is needed.

### An unrelated request

Add an explicit category when unsupported requests should receive a help reply:

```python
from decisionact import Intent

other = Intent(
    desc="Any request unrelated to greetings or addition",
    outcomes=["help"],
)

print(other.outcomes)
```

Output:

```text
['help']
```

There is no automatic out-of-scope category. `"other"` is a name you choose, and
`help` must be a registered outcome. Tailor its description to the requests your
agent actually supports; the greeting-only agent below uses its own description.

## Using intents in an agent

This complete, independent script gives each intent two possible outcomes. It
prints the input, selected intent, selected outcome, and reply for four messages.
It uses Jev, so set `TYPESAFE_API_KEY` in your environment first:

```python
import os
from decisionact import Agent, Intent, Outcome
from decisionact.models import SystemOneModel


if __name__ == "__main__":
    agent = Agent(
        tools=[],
        intents={
            "greeting": Intent(
                desc="The user greets the agent, such as hello or good morning",
                context="Choose morning_welcome for a morning greeting; otherwise choose welcome.",
                outcomes=["welcome", "morning_welcome"],
            ),
            "other": Intent(
                desc="The user asks about capabilities or makes a request unrelated to greetings",
                context="Choose help for usage questions; otherwise choose unsupported.",
                outcomes=["help", "unsupported"],
            ),
        },
        outcomes={
            "welcome": Outcome(
                desc="A greeting that does not specifically mention morning",
                reply="Hello!",
            ),
            "morning_welcome": Outcome(
                desc="The user specifically greets the agent with good morning",
                reply="Good morning!",
            ),
            "help": Outcome(
                desc="The user asks what the agent can do or requests usage help",
                reply="I can respond to greetings. Try hello or good morning.",
            ),
            "unsupported": Outcome(
                desc="The user requests an unsupported task, rather than asking for usage help",
                reply="This demo cannot help with that request.",
            ),
        },
        model=SystemOneModel(api_key=os.getenv("TYPESAFE_API_KEY")),
    )
    messages = ["Hello", "Good morning", "What can you do?", "What is the weather?"]
    for index, message in enumerate(messages, start=1):
        result = agent.turn(message=message, session_id=f"intent-demo-{index}")
        print(f"Input: {message}")
        print(f"Intent: {result.intent}")
        print(f"Outcome: {result.outcome}")
        print(f"Reply: {result.reply}")
        print()
```

One possible run, when model decisions follow the descriptions above:

```text
Input: Hello
Intent: greeting
Outcome: welcome
Reply: Hello!

Input: Good morning
Intent: greeting
Outcome: morning_welcome
Reply: Good morning!

Input: What can you do?
Intent: other
Outcome: help
Reply: I can respond to greetings. Try hello or good morning.

Input: What is the weather?
Intent: other
Outcome: unsupported
Reply: This demo cannot help with that request.
```

The first two messages select the same `greeting` intent but different outcomes.
The last two select `other`, then choose either usage help or an unsupported-task
reply. The model selects an outcome only from the selected intent's list. With
no tools and multiple possible endings, this example makes an intent decision
followed by an outcome decision. Each message uses a separate demo session.

`Agent(...)` validates and stores the configuration. `turn()` makes the provider
request and returns a `TurnResult` for a normal or handled turn. `result.intent`
holds the selected dictionary key. If intent selection is too uncertain, the
agent can return a rephrasing request instead; when no intent has been selected,
`result.intent` remains `None`.

Intent selection uses the model's `min_conf` threshold, which defaults to `0.6`.
Its Choice record appears in `result.decisions` with step `"1. intent"`, the model's
answer, confidence, and a low-confidence flag. See [Decision models](models.md)
for threshold configuration.

The selection state includes the current user message. Previous messages are
included only when [conversation memory](memory-and-checkpoints.md) is enabled;
the default `NoMemory()` supplies no previous messages. Saving conversation
history in a checkpoint does not by itself make that history visible to the model.

When a tool is paused for missing input, send the answer through `turn()` with the
same session ID. The engine checks whether it answers the pending question. If
so, it resumes the stored intent and tool instead of selecting a new intent.
Otherwise, it drops the paused call and selects an intent for the new request.
Pending approval also retains the original intent while review is handled.

When loading a saved missing-input request, the agent discards it if its intent
has been removed from the current configuration. The same cleanup applies if its
tool or parameter no longer exists. Keep this in mind when renaming definitions
used by saved conversations.

Model decisions are probabilistic. Provider exceptions can propagate rather than
returning a normal `TurnResult`; see the model documentation for error behavior.

## Related pages and API

- [Tools](tools.md): define and register functions an intent can use.
- [Parameters](parameters.md): resolve the selected tool's inputs.
- [Outcomes](outcomes.md): define possible endings and reply templates.
- [Decision models](models.md): configure Jev or Cloudflare Clef.
- [Execution flow](execution-flow.md): selection and continuation during a turn.
- [Intent API reference](api-reference.md#tools-inputs-intents-and-outcomes): signatures and configuration errors.
