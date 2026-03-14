# AGENTS.md — Workstream B: `engine/`

## Your Job

You own everything that consumes `AdapterContext` and produces evaluated results.
You do not need to know how markets are fetched or how adapters work. You receive
a fully populated `AdapterContext` and a `MarketSnapshot`, and you return a list
of `AgentEvalResult` objects.

## What You Build

```
engine/
├── __init__.py                  # Public interface: run_evaluation()
├── replay_engine.py             # Splits price history at replay timestamp
├── agents/
│   ├── base_agent.py            # Abstract agent interface
│   ├── llm_agent.py             # Claude + GPT-4o implementations
│   └── baseline_agent.py        # Market baseline (echoes market probability)
├── position_manager.py          # Entry/exit timing simulation
└── metrics.py                   # Brier score, PnL, edge vs market
```

## Your Public Interface

This is the only function Workstream C calls. Implement it in `engine/__init__.py`.
Do not change the signature without telling Workstreams A and C.

```python
from shared.types import AdapterContext, MarketSnapshot, AgentEvalResult

def run_evaluation(
    context: AdapterContext,
    market: MarketSnapshot,
) -> list[AgentEvalResult]:
    """
    Given a fully populated AdapterContext and its source MarketSnapshot,
    runs the replay engine, dispatches all registered agents, simulates
    positions, and returns one AgentEvalResult per agent.

    The MarketSnapshot passed in contains full price history including
    future prices (after replay_timestamp). The replay engine is responsible
    for hiding future prices from agents.
    """
    ...
```

## Shared Types You Use

```python
from shared.types import (
    AdapterContext, MarketSnapshot, PricePoint,
    TradingSignal, EntryCondition, ExitCondition,
    SimulatedPosition, AgentEvalResult
)
```

## Replay Engine

The replay engine splits price history at `context.replay_timestamp`:
- Agents see only the past (up to and including replay_timestamp)
- Evaluation uses the future (after replay_timestamp) to score decisions

```python
# engine/replay_engine.py

from dataclasses import dataclass
from datetime import datetime
from shared.types import AdapterContext, MarketSnapshot, PricePoint

@dataclass
class ReplayState:
    context: AdapterContext             # Contains only past price history
    market: MarketSnapshot              # Full market including metadata
    replay_timestamp: datetime
    probability_at_replay: float
    future_price_history: list[PricePoint]
    final_resolution: bool | None

def build_replay_state(
    context: AdapterContext,
    market: MarketSnapshot,
) -> ReplayState:
    replay_ts = context.replay_timestamp
    past = [p for p in market.price_history if p.timestamp <= replay_ts]
    future = [p for p in market.price_history if p.timestamp > replay_ts]

    if not past:
        raise ValueError("No price history before replay timestamp")

    probability_at_replay = past[-1].probability

    # Build a past-only context so agents cannot see future prices
    past_context = AdapterContext(
        market_id=context.market_id,
        market_question=context.market_question,
        market_type=context.market_type,
        current_probability=probability_at_replay,
        price_history=past,
        context_documents=context.context_documents,
        metadata=context.metadata,
        replay_timestamp=replay_ts,
        resolution=None             # Agent does not know outcome
    )

    return ReplayState(
        context=past_context,
        market=market,
        replay_timestamp=replay_ts,
        probability_at_replay=probability_at_replay,
        future_price_history=future,
        final_resolution=market.resolution
    )
```

## Agent Interface

All agents implement `BaseAgent`. The model backing an agent is an implementation detail.

```python
# engine/agents/base_agent.py

from abc import ABC, abstractmethod
from shared.types import AdapterContext, TradingSignal

class BaseAgent(ABC):
    agent_id: str

    @abstractmethod
    def trade(self, context: AdapterContext) -> TradingSignal:
        ...
```

## Agent Prompt Contract

All LLM agents must use this exact prompt. Do not deviate from the structure --
consistent output format is required for the parser to work across models.

```
SYSTEM:
You are a prediction market trading agent. You reason carefully about probability,
information asymmetry, and market pricing. You always output valid JSON only, with
no preamble or markdown fences.

USER:
Market Question: {market_question}
Market Type: {market_type}
Current Market Probability (YES): {current_probability:.1%}
Your Analysis Date: {replay_timestamp}
Days to Resolution: {days_to_resolution}

--- CONTEXT ---
{context_documents joined by "\n\n---\n\n"}
--- END CONTEXT ---

1. Estimate the true probability of YES resolution.
2. Decide whether to trade YES, NO, or PASS.
3. Specify entry timing: immediately, or wait for a specific price threshold.
4. Specify exit timing: price target, time limit, stop loss, or hold to resolution.
   Consider exiting early if you expect the market to reprice before resolution.
5. Provide a concise rationale (3-5 sentences).

Respond ONLY with this JSON object:
{
  "estimated_probability": float,
  "direction": "YES" | "NO" | "PASS",
  "confidence": float,
  "entry_condition": {
    "trigger": "immediate" | "price_threshold" | "time_threshold",
    "threshold": float | null,
    "rationale": string
  },
  "exit_condition": {
    "trigger": "price_target" | "time_limit" | "stop_loss" | "to_resolution",
    "price_target": float | null,
    "time_limit": "ISO date string" | null,
    "stop_loss": float | null,
    "rationale": string
  },
  "hold_horizon": "immediate" | "short" | "long" | "to_resolution",
  "rationale": string
}
```

Parse the response by stripping any accidental markdown fences before `json.loads()`.

## Registered Agents

Register agents in `engine/__init__.py`. Add or remove agents here only.

```python
from engine.agents.llm_agent import LLMAgent
from engine.agents.baseline_agent import MarketBaselineAgent

AGENTS = [
    LLMAgent("claude-sonnet", "claude-sonnet-4-20250514", provider="anthropic"),
    LLMAgent("gpt-4o", "gpt-4o", provider="openai"),
    MarketBaselineAgent(),
]
```

The `MarketBaselineAgent` always runs. It echoes market probability with direction PASS
and zero rationale. It is the benchmark every other agent is compared against.

## Position Manager

The position manager simulates realistic PnL by respecting the `EntryCondition`
and `ExitCondition` from each `TradingSignal`. It walks the future price history
point by point to determine when entry and exit conditions trigger.

Entry logic:
- `"immediate"`: enter at `probability_at_replay`
- `"price_threshold"`: scan future history; enter when price crosses threshold
  in the direction favorable to the trade (below threshold for YES, above for NO)

Exit logic (checked in order after entry):
- `"price_target"`: exit when price reaches target in favorable direction
- `"stop_loss"`: exit when position loss exceeds stop threshold
- `"time_limit"`: exit at or after the specified datetime
- `"to_resolution"`: hold until final resolution

Also always compute `resolution_pnl` — what the position would have returned
if held to resolution regardless of the exit condition. This lets the dashboard
show whether early exits helped or hurt.

PnL formula (assume $1 position size):
- YES position: `pnl = exit_price - entry_price`
- NO position: `pnl = entry_price - exit_price`
- PASS or no entry triggered: `pnl = 0.0`

## Evaluation Metrics

Implement in `engine/metrics.py`:

| Metric | Formula |
|---|---|
| Brier Score | `(estimated_probability - float(resolution))^2`. None if unresolved. |
| Edge vs Market | `estimated_probability - probability_at_replay` |
| Directional Accuracy | Did agent correctly predict direction of final price movement? None if PASS or unresolved. |
| Simulated PnL | From position_manager using entry/exit conditions |
| Resolution PnL | From position_manager assuming hold to resolution |

## Testing Without the Pipeline

Workstream B can test independently using a mock `AdapterContext`:

```python
from datetime import datetime
from shared.types import AdapterContext, PricePoint

mock_context = AdapterContext(
    market_id="test-market",
    market_question="Will the Fed cut rates in June 2025?",
    market_type="long_horizon",
    current_probability=0.42,
    price_history=[
        PricePoint(datetime(2025, 4, 1), 0.38),
        PricePoint(datetime(2025, 4, 15), 0.42),
    ],
    context_documents=[
        "SITUATION SUMMARY:\nThe Fed has held rates steady...",
        "BULL CASE:\nInflation is cooling faster than expected...",
        "BEAR CASE:\nLabor market remains tight...",
    ],
    metadata={"days_to_resolution": 45},
    replay_timestamp=datetime(2025, 4, 15),
    resolution=None
)

from engine import run_evaluation
# You also need a mock MarketSnapshot with full price history for replay
```

## Rules

- Do not import from `pipeline/` or `app/`.
- Do not fetch market data. You receive `AdapterContext` and `MarketSnapshot` fully populated.
- Do not define dataclasses outside of `shared/types.py`.
- Always include `MarketBaselineAgent` in every evaluation run.
- Always compute both `simulated_pnl` (with entry/exit) and `resolution_pnl` (hold to end).
- A `PASS` signal is valid. Do not penalize it -- return `pnl = 0.0` and `exit_reason = "no_entry"`.
