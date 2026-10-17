# Middleware and human approval

Middleware inspects a selected tool call after its inputs are resolved and before
it executes. The built-in approval middleware pauses selected actions until a
person approves or rejects them.

## Define middleware

This independent declaration logs a tool name before execution:

```python
from decisionact.middleware import Middleware


class ToolNames(Middleware):
    def before_tool(self, agent, sess, intent, tool, args, calls):
        print("Running tool:", tool.name)
```

Pass an instance through `Agent(middleware=[ToolNames()])`. Returning normally
permits the call. Hooks run in the order supplied in the middleware list.

| Hook | Called when |
| --- | --- |
| `validate(agent)` | Once after the agent configuration is checked. |
| `before_tool(agent, sess, intent, tool, args, calls)` | Before the selected function runs. |
| `answer_interrupt(sess, message)` | A new message arrives while approval is pending. |

`calls` contains earlier `(tool_name, inputs, output)` entries for the turn.
Raising `Interrupt(reply)` stops execution; a custom interrupt needs its own saved
state and continuation mechanism. The built-in approval middleware provides those
for human review.

## Add human approval

This complete, standalone example saves a title in an in-memory notes list only
after approval. It uses Jev, so set `TYPESAFE_API_KEY` before running it. The demo
acts as the reviewer and immediately approves; an application can wait for a
reviewer's decision before calling `resume()`.

```python
import os
from decisionact import Agent, Intent, Outcome, Param, tool
from decisionact.middleware import Approval, HumanInTheLoopMiddleware, approve
from decisionact.models import SystemOneModel

NOTES = []


@tool(title=Param(desc="The note title"))
def save_note(title):
    """Save a note title to the demo list and return it."""
    NOTES.append(title)
    return {"title": title}


if __name__ == "__main__":
    approval = HumanInTheLoopMiddleware(approvals={
        "save_note": Approval(
            rejected_outcome="note_rejected",
            waiting="Saving {title} needs approval.",
        )
    })
    agent = Agent(
        tools=[save_note],
        intents={
            "save": Intent(
                desc="Save a note",
                context="Call save_note once, then finish with saved.",
                tools=["save_note"],
                outcomes=["saved"],
            ),
            "other": Intent(desc="Requests unrelated to saving notes", outcomes=["help"]),
        },
        outcomes={
            "saved": Outcome(desc="The note was saved", reply="Saved note {title}."),
            "note_rejected": Outcome(desc="The reviewer declined", reply="Not saved: {rejection_reason}."),
            "help": Outcome(desc="The request is outside this demo", reply="Ask me to save a note."),
        },
        model=SystemOneModel(api_key=os.getenv("TYPESAFE_API_KEY")),
        middleware=[approval],
    )
    result = agent.turn(message="Save a note titled Reminder", session_id="review-demo")
    print(result.reply)
    if result.pending_approval:
        print(result.pending_approval.tool, result.pending_approval.inputs)
        result = agent.resume(session_id="review-demo", decision=approve())
        print(result.reply)
```

On a successful decision path, the first result has outcome `awaiting_approval`
and `NOTES` has not changed. After approval, the saved function executes and the
engine selects its ending. The rejection outcome must be registered with the
agent, but does not need to be offered in `Intent.outcomes`.

## Approve, reject, or wait

In the previous example, replace the approval call with the following to decline
the same pending action instead. Approve and reject are alternatives:

```python
from decisionact.middleware import reject

result = agent.resume(session_id="review-demo", decision=reject("Keep this as a draft"))
```

Rejection skips the pending tool. `{rejection_reason}`, its resolved inputs, and
previous tool output are available to the rejection template. Calling `resume()`
without a pending approval raises `ValueError`.

A chat interface can alternatively send `/approve` or `/reject [reason]` through
`agent.turn(..., session_id=...)`. Matching is case-insensitive and requires no
model decision. Other messages return the waiting reply without running the tool.

## Persistence and access

The default checkpoint is an in-memory SQLite database. For review that must
survive a restart, pass a file-based checkpointer as described in
[memory and checkpoints](memory-and-checkpoints.md).

Approval commands do not authenticate the sender: anyone who can send messages to
that session can answer. Apply your application's access controls or use a
separate reviewer integration with `resume()`.

## Behavior and limitations

- Rules map registered tool names to `Approval` objects and must not be empty.
- Rejection outcomes must exist in the agent's outcome dictionary.
- Middleware controls the next tool call; it does not undo earlier actions.
- Approving a call skips approval for that call when it resumes; later tools can
  still require their own approvals.
- The demo's `NOTES` list resets with the process. Conversation checkpoints do
  not persist a tool's business data.

## Related API

See [middleware and approval signatures](api-reference.md#middleware-and-approval)
and [approval execution flow](execution-flow.md#continue-an-approval).
