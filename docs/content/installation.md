# Installation

Install DecisionAct before following the quickstart. You need Python 3.10 or newer
and a provider account for the decision model you choose.

## Install with pip

In your Python environment:

```bash
pip install decisionact
```

## Install with uv

Inside a uv project:

```bash
uv add decisionact
```

## Included dependencies

The package installs `httpx` and the TypeSafe SDK. Jev uses the SDK; Cloudflare
Clef uses the HTTP client. Models run on their providers' servers, so no model
weights or model-specific local runtimes are downloaded.

SQLite support comes with Python. You do not need a separate database package
to use `SqliteCheckpointer`.

## Verify the installation

Run this in the same Python environment where you installed the package:

```bash
python -c "import decisionact; print(decisionact.__version__)"
```

For a uv project:

```bash
uv run python -c "import decisionact; print(decisionact.__version__)"
```

Importing the package does not contact a model provider. The installed version
is printed; the current documented API is v0.1.1.

## Configure a decision model

The [quickstart](quickstart.md) shows how to set `TYPESAFE_API_KEY` and initialize
Jev. The [decision models guide](models.md) covers both Jev and Cloudflare Clef,
including Cloudflare's API token and account ID.

Keep credentials in your environment rather than committing them to source
control. Credentials and model access are required when you run an agent turn.

Continue to [Quickstart](quickstart.md) for a complete working agent.
