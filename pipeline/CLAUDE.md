# AGENTS.md — Workstream A: `pipeline/`

## Your Job

You own everything that touches external APIs and produces `AdapterContext`.
Your output is consumed by Workstream B (engine) and C (app) through a single
callable interface. You do not need to know anything about how agents work
or how the dashboard renders.

## What You Build

```
pipeline/
├── __init__.py                  # Public interface: build_context()
├── polymarket_client.py         # Fetches MarketSnapshot from Polymarket API
├── classifier.py                # Routes market question to adapter type
├── adapters/
│   ├── base_adapter.py          # Abstract base class
│   ├── long_horizon_adapter.py  # News + macro briefing via web search
│   └── speech_adapter.py        # Transcript + word frequency analysis
└── scripts/
    └── prefetch_markets.py      # Cache markets to data/cache/ before demo
```

## Your Public Interface

This is the only function Workstream C calls. Implement it in `pipeline/__init__.py`.
Do not change the signature without telling Workstreams B and C.

```python
from datetime import datetime
from shared.types import AdapterContext, MarketSnapshot

def build_context(
    slug: str,
    replay_timestamp: datetime
) -> tuple[AdapterContext, MarketSnapshot]:
    """
    Fetches market data for `slug`, classifies the market type,
    runs the appropriate adapter, and returns a fully populated
    AdapterContext alongside the raw MarketSnapshot.

    `replay_timestamp` is the point in time the agent will reason from.
    The MarketSnapshot returned should have price history up to and
    including replay_timestamp only — do not leak future prices.
    """
    ...
```

## Shared Types You Use

Import only from `shared.types`. Do not define your own dataclasses.

```python
from shared.types import MarketSnapshot, AdapterContext, PricePoint
```

## Polymarket API

Use the Polymarket CLOB and Gamma REST APIs. No authentication required for reads.

```python
CLOB_BASE = "https://clob.polymarket.com"
GAMMA_BASE = "https://gamma-api.polymarket.com"

# Fetch market metadata
GET {GAMMA_BASE}/markets?slug={slug}

# Fetch YES token price history
GET {CLOB_BASE}/prices-history?token_id={yes_token_id}&interval=1d&fidelity=60
```

Price history entries look like: `{"t": unix_timestamp, "p": probability_float}`

Convert these to `PricePoint(timestamp=datetime.fromtimestamp(t), probability=p)`.

## Market Classifier

Use a Claude API call with strict JSON output to route a market question to one
of the supported adapter types.

```python
MARKET_TYPES = ["long_horizon", "speech", "unknown"]
```

Output schema:
```json
{"market_type": "long_horizon", "confidence": 0.92, "reasoning": "one sentence"}
```

If confidence is below 0.6 or market_type is "unknown", fall back to the
long_horizon adapter -- it is the most general-purpose.

## Long-Horizon Adapter

Use Claude with the web search tool to build a structured research briefing.
The briefing should cover: situation summary, bull case, bear case, historical
base rate, key dates, and uncertainty factors.

Format the output as a list of `context_documents` strings -- one section per
string. The engine agent prompt will join them with `\n\n---\n\n`.

Example context_documents structure:
```python
[
    "SITUATION SUMMARY:\n...",
    "BULL CASE (YES more likely):\n...",
    "BEAR CASE (NO more likely):\n...",
    "HISTORICAL BASE RATE:\n...",
    "KEY UNCERTAINTY FACTORS:\n- factor1\n- factor2",
]
```

## Speech Adapter

Two-step process:
1. Extract speaker name, target phrase, and event type from the market question
   using a Claude call.
2. Use Claude with web search to find historical speech transcripts and analyze
   word/phrase frequency and contextual usage patterns for that speaker.

context_documents structure:
```python
[
    "TARGET PHRASE: '<phrase>'",
    "SPEAKER: <name>",
    "HISTORICAL USAGE FREQUENCY: <description>",
    "TYPICAL USAGE CONTEXTS:\n- context1\n- context2",
    "CURRENT EVENT RELEVANCE:\n...",
    "RECENT EXAMPLES:\n- date: example",
    "ADAPTER BASE RATE ESTIMATE: <float>",
]
```

## Prefetch Script

**Run this before the demo.** Caches all markets to `data/cache/<slug>.json`.
The cache files contain the full `MarketSnapshot` serialized to JSON.

`build_context()` should check `data/cache/<slug>.json` before hitting the API,
and fall back to live fetch only if the cache file does not exist.

```python
# Cache check pattern in polymarket_client.py
import json
from pathlib import Path

CACHE_DIR = Path("data/cache")

def fetch_market(slug: str) -> MarketSnapshot:
    cache_path = CACHE_DIR / f"{slug}.json"
    if cache_path.exists():
        with open(cache_path) as f:
            return deserialize_market(json.load(f))
    # ... live fetch ...
```

## Rules

- Do not import from `engine/` or `app/`.
- Do not produce `TradingSignal` objects. That is the engine's job.
- Do not put agent reasoning logic inside adapters.
- Adapters may call LLMs to build context (web search briefings are fine).
- All dataclasses come from `shared/types.py` only.
- Every adapter must return a fully populated `AdapterContext` with at least
  one non-empty string in `context_documents`.

## Testing Without the Engine

You can test your output independently:

```python
# Quick smoke test
from datetime import datetime
from pipeline import build_context

context, market = build_context(
    "will-the-fed-cut-rates-in-june-2025",
    datetime(2025, 5, 1)
)
print(context.market_type)
print(len(context.context_documents))
for doc in context.context_documents:
    print(doc[:100])
```

## Suggested Market Slugs to Pre-fetch

Find real slugs by browsing polymarket.com and copying from the URL.
Aim for:
- 3-5 long_horizon markets: macro events, product launches, policy decisions
- 3-5 speech markets: "will [person] say [word] in [event]" format

Resolved markets are preferable for pre-fetching because `resolution` will be
set to True or False, enabling full evaluation including Brier score.
