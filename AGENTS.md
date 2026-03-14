# AGENTS.md — MarketAdapters Arena

## Project Overview

MarketAdapters Arena is a market-type-aware AI evaluation and trading intelligence platform
for Polymarket. The system classifies prediction markets into reasoning categories, constructs
domain-specific context pipelines (adapters) for each type, and evaluates multiple AI agents
against historical market states using a replay engine.

The MVP targets two adapter types: long-horizon reasoning and speech/language prediction.
The agent competition layer runs multiple models simultaneously, comparing their probability
estimates, entry/exit timing, and simulated PnL against each other and against the market's
own historical pricing as a baseline.

---

## Repository Structure

```
marketadapters-arena/
├── AGENTS.md                        # This file — root-level overview
├── IMPLEMENTATION.md                # Full implementation guide
├── README.md
├── .env.example
├── pyproject.toml
├── data/
│   ├── cache/                       # Pre-fetched market JSON (Workstream A writes, all read)
│   └── results.json                 # Evaluation output (Workstream C writes, C reads)
│
├── shared/                          # SHARED CONTRACT — read by all, edited by nobody alone
│   ├── __init__.py
│   └── types.py                     # All dataclasses: AdapterContext, TradingSignal, etc.
│
├── pipeline/                        # WORKSTREAM A: Data, adapters, classifier
│   ├── AGENTS.md
│   ├── __init__.py                  # Exposes build_context() — the only public interface
│   ├── polymarket_client.py
│   ├── classifier.py
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── base_adapter.py
│   │   ├── long_horizon_adapter.py
│   │   └── speech_adapter.py
│   ├── scripts/
│   │   └── prefetch_markets.py
│   └── tests/
│       └── test_adapters.py
│
├── engine/                          # WORKSTREAM B: Agents, replay, evaluation
│   ├── AGENTS.md
│   ├── __init__.py                  # Exposes run_evaluation() — the only public interface
│   ├── replay_engine.py
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base_agent.py
│   │   ├── llm_agent.py
│   │   └── baseline_agent.py
│   ├── position_manager.py
│   ├── metrics.py
│   └── tests/
│       └── test_engine.py
│
└── app/                             # WORKSTREAM C: Orchestration, dashboard
    ├── AGENTS.md
    ├── __init__.py
    ├── main.py                      # Entrypoint — wires pipeline + engine
    ├── dashboard.py                 # Streamlit leaderboard UI
    └── tests/
        └── test_integration.py
```

---

## The Shared Contract

**`shared/types.py` is the single source of truth for all data structures.**

No workstream defines its own dataclasses. If you need to add a field, coordinate
with both other people before touching this file. Treat it like a public API:
additive changes (new optional fields with defaults) are safe, renaming or removing
fields breaks everyone.

```python
# shared/types.py

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class PricePoint:
    timestamp: datetime
    probability: float


@dataclass
class MarketSnapshot:
    market_id: str
    question: str
    outcomes: list[str]
    yes_price: float
    price_history: list[PricePoint]
    end_date: datetime | None
    resolved: bool
    resolution: bool | None         # True = YES, False = NO, None = unresolved


@dataclass
class AdapterContext:
    market_id: str
    market_question: str
    market_type: str                # "long_horizon" | "speech" | "unknown"
    current_probability: float
    price_history: list[PricePoint]
    context_documents: list[str]    # Ordered text blocks for the agent prompt
    metadata: dict
    replay_timestamp: datetime
    resolution: bool | None


@dataclass
class EntryCondition:
    trigger: str                    # "immediate" | "price_threshold" | "time_threshold"
    threshold: float | None
    rationale: str


@dataclass
class ExitCondition:
    trigger: str                    # "price_target" | "time_limit" | "stop_loss" | "to_resolution"
    price_target: float | None
    time_limit: datetime | None
    stop_loss: float | None
    rationale: str


@dataclass
class TradingSignal:
    agent_id: str
    market_id: str
    estimated_probability: float
    direction: str                  # "YES" | "NO" | "PASS"
    confidence: float
    entry_condition: EntryCondition
    exit_condition: ExitCondition
    hold_horizon: str               # "immediate" | "short" | "long" | "to_resolution"
    rationale: str
    raw_response: str


@dataclass
class SimulatedPosition:
    agent_id: str
    market_id: str
    direction: str
    entry_price: float | None
    exit_price: float | None
    entry_timestamp: datetime | None
    exit_timestamp: datetime | None
    exit_reason: str                # "price_target" | "stop_loss" | "time_limit" | "resolution" | "no_entry"
    pnl: float
    resolution_pnl: float


@dataclass
class AgentEvalResult:
    agent_id: str
    market_id: str
    market_question: str
    market_type: str
    brier_score: float | None
    edge_vs_market: float
    directional_correct: bool | None
    simulated_pnl: float
    resolution_pnl: float
    exit_reason: str
    estimated_probability: float
    market_probability: float
    final_resolution: bool | None
    rationale: str
```

---

## Integration Points

These are the only two places where workstreams connect.
Agree on these signatures before splitting up and do not change them without
telling everyone.

```python
# pipeline/__init__.py — Workstream A delivers this
def build_context(slug: str, replay_timestamp: datetime) -> tuple[AdapterContext, MarketSnapshot]:
    ...

# engine/__init__.py — Workstream B delivers this
def run_evaluation(
    context: AdapterContext,
    market: MarketSnapshot,
) -> list[AgentEvalResult]:
    ...
```

Workstream C imports exactly these two functions and nothing else from A or B:

```python
# app/main.py
from pipeline import build_context
from engine import run_evaluation
```

---

## Workstream Responsibilities

### Workstream A — `pipeline/`
Owns everything that touches external APIs and produces `AdapterContext`.

Consumes from shared: `MarketSnapshot`, `AdapterContext`, `PricePoint`
Does not touch: `engine/` or `app/`

### Workstream B — `engine/`
Owns everything that consumes `AdapterContext` and produces evaluated results.

Consumes from shared: All types except none — uses the full shared contract.
Does not touch: `pipeline/` or `app/`

### Workstream C — `app/`
Owns the entrypoint and dashboard. Wires A and B together.
Can build the dashboard independently using mock `AgentEvalResult` data
before A and B finish. Does not need either workstream complete to make progress.

Consumes from shared: `AgentEvalResult` (for rendering)
Does not touch: `pipeline/` or `engine/`

---

## Architecture Principles

1. Adapters are pure data pipelines. They may make LLM calls for context construction
   but must never produce `TradingSignal` outputs.
2. Agents are model-agnostic. The backing model is an implementation detail.
3. The replay engine is the source of truth. Never evaluate on live markets during demo.
4. Entry and exit are first-class outputs. `TradingSignal` must always include both.
5. The market baseline is always present. It echoes historical market probability.
6. Cache everything before the demo. No live Polymarket calls during the presentation.

---

## What NOT to Do

- Do not define dataclasses outside of `shared/types.py`.
- Do not import across workstream folders directly. Only import from `shared/`.
  Workstream C is the only code that imports from both `pipeline/` and `engine/`.
- Do not let adapters produce `TradingSignal` outputs.
- Do not evaluate agents only on final resolution. Always use the dual comparison.
- Do not make live API calls during the demo presentation.

---

## MVP Scope

In scope:
- Long-horizon adapter (news context via Claude web search)
- Speech adapter (transcript retrieval and word frequency analysis)
- Market classifier (Claude-based routing)
- Replay engine with 5-10 pre-fetched historical markets per type
- Two agents: Claude Sonnet, GPT-4o, plus market baseline
- Entry/exit timing simulation in position manager
- Streamlit leaderboard with reasoning trace viewer

Out of scope for MVP:
- Live trading
- Sports, crypto threshold, or regulatory adapters
- Adaptive agent training
- Portfolio-level evaluation
- User accounts or persistence beyond a local run
