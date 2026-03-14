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
