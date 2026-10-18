# Memory and checkpoints

Memory decides which previous messages a decision model sees. A checkpointer stores
conversation state between turns. These are separate responsibilities: reducing
model context does not delete saved history.

## Memory chooses what the model sees

This complete local example shows the selection behavior without any API request:

```python
from decisionact.memory import ConversationBufferMemory, NoMemory

history = [
    ("user", "Hello"),
    ("agent", "Hello!"),
    ("user", "What did I say?"),
]

memory = ConversationBufferMemory(k=2)
print(memory.messages(history))
print(NoMemory().messages(history))
```

Output:

```text
[('user', 'Hello'), ('agent', 'Hello!')]
[]
```

The final history entry is the current user message; the engine adds it separately
to decision state. `k` counts individual messages, not user/agent pairs.

| Setting | Context supplied to the model |
| --- | --- |
| `NoMemory()` | No previous messages; this is the agent default. |
| `ConversationBufferMemory(k=7)` | Up to seven previous individual messages. |
| `ConversationBufferMemory()` | All previous messages, subject to per-step limits. |

Optional-input detection sees at most four previous messages, even with a larger
buffer. Memory can help interpret follow-ups but does not guarantee the right decision.

## SQLite stores the conversation

Pass `SqliteCheckpointer(path="conversations.db")` as `checkpointer=` on `Agent` to save
conversation state in a file. SQLite comes with Python. Saved state includes
history, resolved inputs, paused questions, and pending approvals.

Checkpointing is disabled by default. Omit `checkpointer` or pass
`checkpointer=None` to keep sessions in plain Python memory without creating a
checkpointer, SQLite connection, database, or checkpoint files. History, collected
inputs, missing-input follow-ups, and pending approvals remain available within
the same agent instance, but are lost when it is discarded or the process restarts.
Memory still controls which history the model sees; it does not enable persistence.
Pass a checkpointer explicitly when you need it. File-based checkpoints survive
process restarts; `SqliteCheckpointer(path=":memory:")` is an explicit temporary option.

## Complete configuration example

This standalone greeting agent uses a conversation buffer and SQLite. Set
`TYPESAFE_API_KEY` in your environment before running it. It does not import a
quickstart or example file:

```python
import os
from decisionact import Agent, Intent, Outcome
from decisionact.checkpoint import SqliteCheckpointer
from decisionact.memory import ConversationBufferMemory
from decisionact.models import SystemOneModel


if __name__ == "__main__":
    storage = SqliteCheckpointer(path="conversations.db")
    try:
        agent = Agent(
            tools=[],
            intents={
                "greeting": Intent(desc="The user says hello", outcomes=["welcome"]),
                "other": Intent(desc="Requests unrelated to greetings", outcomes=["help"]),
            },
            outcomes={
                "welcome": Outcome(desc="A greeting was received", reply="Hello!"),
                "help": Outcome(desc="The request is outside this demo", reply="Try saying hello."),
            },
            model=SystemOneModel(api_key=os.getenv("TYPESAFE_API_KEY")),
            memory=ConversationBufferMemory(k=7),
            checkpointer=storage,
        )
        result = agent.turn(message="Hello", session_id="memory-demo")
        print(result.reply)
        print(agent.history(session_id="memory-demo"))
    finally:
        storage.close()
```

With successful decisions, the reply is `Hello!`. History is a list of `(role,
text)` tuples. Reusing `memory-demo` with the same database continues that session;
use a distinct session ID for each separate conversation.

## History, reset, and shutdown

Inside the example's `try` block, while storage is still open, these calls inspect
and clear only the selected session:

```python
history = agent.history(session_id="memory-demo")
agent.reset(session_id="memory-demo")
```

Reset deletes saved conversation state; it does not undo tool effects or clear your
application's business data. Close the SQLite connection only after every agent
using it has finished.

## Behavior and limitations

- `k` must be a positive integer or `None`.
- Memory chooses context; checkpoints store the full session independently.
- Serialize concurrent turns for the same session in your application.
- A checkpoint does not store your tools' external databases or in-memory business data.
- Saved values must be JSON-serializable. Database and serialization errors can propagate.
- Checkpointing is not a transaction over tool effects. A provider failure after a
  tool runs does not automatically roll it back or create a recovery state.

## Related API

See [Memory](api-reference.md#memory), [checkpoints and Session](api-reference.md#checkpoints-and-session),
and [approval persistence](middleware-and-approval.md).
