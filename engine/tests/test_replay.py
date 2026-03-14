"""
Phase 1 milestone: instantiate a ReplayState and print it from the command line.

Run from repo root:
    PYTHONPATH=. python engine/tests/test_replay.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from datetime import datetime
from shared.types import AdapterContext, MarketSnapshot, PricePoint
from engine.replay_engine import build_replay_state
from engine.agents.baseline_agent import MarketBaselineAgent

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

mock_market = MarketSnapshot(
    market_id="test-market",
    question="Will the Fed cut rates in June 2025?",
    outcomes=["Yes", "No"],
    yes_price=0.42,
    price_history=[
        PricePoint(datetime(2025, 4, 1), 0.38),
        PricePoint(datetime(2025, 4, 15), 0.42),
        PricePoint(datetime(2025, 5, 1), 0.55),
        PricePoint(datetime(2025, 6, 1), 0.72),
    ],
    end_date=datetime(2025, 6, 30),
    resolved=True,
    resolution=True
)

if __name__ == "__main__":
    print("=== Building ReplayState ===")
    state = build_replay_state(mock_context, mock_market)
    print(state)

    print("\n=== MarketBaselineAgent signal ===")
    agent = MarketBaselineAgent()
    signal = agent.trade(state.context)
    print(signal)

    print("\n=== Checks ===")
    assert state.probability_at_replay == 0.42
    assert len(state.future_price_history) == 2
    assert state.final_resolution is True
    assert state.context.resolution is None  # agent cannot see outcome
    assert signal.direction == "PASS"
    assert signal.estimated_probability == 0.42
    print("All checks passed.")
