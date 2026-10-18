# Flight desk agent

This complete repository example shows DecisionAct tools, intents, outcomes,
conversation memory, and human approval using fictional business data.

## Capabilities

Search fictional flights, book a flight, inspect bookings, change travel dates,
cancel a booking, add baggage, and select a seat. Tools validate dates, booking
state, and other business constraints.

- **Tools:** `search_flights`, `book_flight`, `get_booking`, `change_flight`,
  `cancel_booking`, `add_baggage`, `select_seat`.
- **Memory:** conversation context helps resolve follow-up requests.
- **Approval:** selected actions can pause before execution.
- **Storage:** checkpointing is disabled by default; sessions stay in Python memory.
  Explicit file-based checkpoint initialization is left commented out.

[View the complete flight desk agent →](https://github.com/Anil951/decisionact/blob/main/examples/flight_desk_agent.py)

```text
Show my bookings.
What is the status of booking BK1001?
```

Use booking IDs and route names from the example’s current demo data.

## Model setup

Both examples initialize Jev using the environment’s `TYPESAFE_API_KEY` and
include commented initialization for the Cloudflare Clef model. They also use
`python-dotenv` to load local environment settings; that helper is an example
dependency, not required by the minimal quickstart.

Never commit provider credentials. The fictional data resets when the example
process restarts; conversation checkpoints do not persist the business data.

## Related concepts

Read [tools](tools.md), [parameters](parameters.md), [intents](intents.md), and
[outcomes](outcomes.md) for independent explanations of the building blocks.
[Memory](memory-and-checkpoints.md) and [middleware](middleware-and-approval.md)
explain context, persistence, and approval without depending on a business example.

The [order agent walkthrough](order-agent.md) shows a smaller application of the
same concepts. The flight desk source above remains the complete example for
flight-specific validation and workflows.
