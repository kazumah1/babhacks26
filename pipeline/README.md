# pipeline/

Workstream A — owns everything that touches external APIs and produces `AdapterContext`.

## Files

```
pipeline/
├── __init__.py                  Public interface: build_context()
├── polymarket_client.py         Fetches MarketSnapshot from Polymarket API (cache-first)
├── classifier.py                Routes market question to adapter type via Claude
├── adapters/
│   ├── _utils.py                extract_json() helper for robust LLM output parsing
│   ├── base_adapter.py          Abstract BaseAdapter class
│   ├── long_horizon_adapter.py  News + macro briefing via Claude web search
│   └── speech_adapter.py        Speaker linguistic analysis via Claude web search
└── scripts/
    └── prefetch_markets.py      Pre-caches market data to data/cache/ before the demo
```

## Public Interface

```python
from pipeline import build_context
from datetime import datetime

context, market = build_context(
    slug="gustavo-petro-out-as-leader-of-colombia-by-june-30",
    replay_timestamp=datetime(2026, 1, 1),
)
# context: AdapterContext with market_type, context_documents, price_history, ...
# market:  raw MarketSnapshot (full price history, resolution status)
```

`build_context` always:
1. Fetches (or loads from cache) the `MarketSnapshot`
2. Classifies the market type via Claude
3. Runs the appropriate adapter to build `context_documents`
4. Filters `price_history` in the returned `AdapterContext` to `<= replay_timestamp`

## Polymarket API Notes

- **Gamma API** (`gamma-api.polymarket.com`): market metadata. `outcomePrices` and
  `clobTokenIds` are JSON strings embedded in the response.
- **CLOB API** (`clob.polymarket.com`): price history. Use `market=<token_id>` (not
  `token_id=`) and `interval=1d&fidelity=60`. Only has data for recently active markets.

## Pre-fetch Script

```bash
python3 -m pipeline.scripts.prefetch_markets
```

Writes 10 markets (5 long-horizon, 5 speech) to `data/cache/`. Run once before the demo.
The cache is never invalidated automatically — delete a `.json` file to force a re-fetch.

## Smoke Tests

```bash
# Imports
python3 -c "from pipeline import build_context; print('OK')"

# Polymarket client (live fetch, then cache hit)
python3 -m pipeline.polymarket_client will-metamask-launch-a-token-by-june-30

# Classifier
python3 -m pipeline.classifier "Will the Fed cut rates in June 2025?"
python3 -m pipeline.classifier "Will Trump say 'tariff' at his next press conference?"
```
