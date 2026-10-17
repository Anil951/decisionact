# Decision models

DecisionAct currently supports Jev and Cloudflare Clef. The adapter supplies typed
decisions to the same `Agent` interface; your tools and intents stay in Python.

## Jev

Set `TYPESAFE_API_KEY` in your environment, then initialize the model:

```python
import os
from decisionact.models import SystemOneModel

# Initialize the Jev decision model.
model = SystemOneModel(
    api_key=os.getenv("TYPESAFE_API_KEY"),
    model="jev-latest",
    min_conf=0.6,
    timeout=30.0,
)
```

The package installs the TypeSafe SDK as a dependency. Initializing the adapter
does not make a provider request. Requests happen when the agent needs a decision.

## Cloudflare Clef

Set `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` in your environment:

```python
import os
from decisionact.models import CloudflareModel

# Initialize the Cloudflare Clef decision model.
model = CloudflareModel(
    api_token=os.getenv("CLOUDFLARE_API_TOKEN"),
    account_id=os.getenv("CLOUDFLARE_ACCOUNT_ID"),
    model="clef",
    min_conf=0.6,
    timeout=30.0,
)
```

The `model` argument selects `clef` or `clef-flash` in the Cloudflare Workers AI
endpoint. The HTTP client is included in the package; no local model installation
is required. Your provider account must have access to the chosen model.

## Connect the adapter to an agent

This complete script uses Jev to run a greeting agent. It needs only the installed
package and `TYPESAFE_API_KEY`; it does not depend on another tutorial file:

```python
import os
from decisionact import Agent, Intent, Outcome
from decisionact.models import SystemOneModel


if __name__ == "__main__":
    model = SystemOneModel(api_key=os.getenv("TYPESAFE_API_KEY"))
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
        model=model,
    )
    result = agent.turn(message="Hello", session_id="model-demo")
    print(result.reply)
```

With successful decisions, the reply is `Hello!`. To use Clef, replace only the
model import and initialization with the Cloudflare configuration above; the
agent configuration is the same. Model requests happen during `turn()`, not when
the adapter is initialized.

## Confidence and timeouts

`min_conf=0.6` sets the threshold for Choice decisions. Noul yes/no decisions use
their own threshold of `0.5` in the engine. `timeout` is measured in seconds.
Evaluate confidence settings with representative requests for your provider.

## Credentials and errors

Missing or blank API keys or model names raise `DecisionModelNotFound` locally.
Mapped provider authentication, permission, and model-not-found responses can
raise the same exception. A missing Cloudflare account ID raises `ValueError`.
Other wrapped request failures raise `DecisionModelError`; malformed responses
can also raise parsing or lookup errors.

Provider errors propagate to your application. A failed turn does not return a
normal `TurnResult` and does not reach the normal checkpoint save step. The
framework does not automatically undo a tool that already ran.

See [model adapter signatures](api-reference.md#model-adapters) for the complete
interface and [execution flow](execution-flow.md#provider-calls-and-errors) for
the request path.
