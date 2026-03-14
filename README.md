# MarketAdapters Arena

A market-type-aware AI evaluation platform for Polymarket. The system classifies
prediction markets into reasoning categories, builds domain-specific context
pipelines (adapters) for each type, and runs multiple AI agents against historical
market states using a replay engine.

## Architecture

```
shared/         Shared dataclasses — single source of truth for all types
pipeline/       Workstream A: data fetching, market classification, adapters
engine/         Workstream B: agents, replay engine, position manager, metrics
app/            Workstream C: orchestration entrypoint, Streamlit dashboard
data/cache/     Pre-fetched market JSON (written by prefetch script, read at runtime)
```

The two integration points between workstreams:

```python
# pipeline/__init__.py
def build_context(slug: str, replay_timestamp: datetime) -> tuple[AdapterContext, MarketSnapshot]: ...

# engine/__init__.py
def run_evaluation(context: AdapterContext, market: MarketSnapshot) -> list[AgentEvalResult]: ...
```

## Quick Start

```bash
# 1. Install dependencies
pip install anthropic httpx streamlit pandas python-dotenv

# 2. Set API keys
cp .env.example .env
# edit .env and add ANTHROPIC_API_KEY and OPENAI_API_KEY

# 3. Pre-fetch market data (required before running the demo)
python3 -m pipeline.scripts.prefetch_markets

# 4. Run the evaluation
python3 app/main.py

# 5. Launch the dashboard
streamlit run app/dashboard.py
```

## Adapter Types

| Type | Markets | Context Source |
|---|---|---|
| `long_horizon` | Policy, macro events, product launches | Claude web search briefing |
| `speech` | Will speaker say word X at event Y | Transcript + frequency analysis via web search |

## Pre-fetched Markets

Run `python3 -m pipeline.scripts.prefetch_markets` to cache all demo markets.
The script fetches 5 long-horizon and 5 speech markets and writes them to
`data/cache/`. No live API calls are made during the demo.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Used by classifier and adapters |
| `OPENAI_API_KEY` | For GPT-4o agent | Used by the GPT-4o agent in engine |
