"""
Smoke test: verifies OpenRouter connectivity and full eval pipeline.
Tests only gemini-flash (fast + cheap) to keep it quick.

Run from repo root:
    python engine/tests/test_openrouter.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()

from datetime import datetime
from shared1.types import AdapterContext, MarketSnapshot, PricePoint
from engine.replay_engine import build_replay_state
from engine.agents.llm_agent import LLMAgent
from engine.position_manager import simulate_position
from engine.metrics import evaluate_agent

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
        "SITUATION SUMMARY:\nThe Fed has held rates steady at 5.25-5.5% for several meetings.",
        "BULL CASE:\nInflation is cooling faster than expected toward the 2% target.",
        "BEAR CASE:\nLabor market remains tight with unemployment near historic lows.",
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
    replay_state = build_replay_state(mock_context, mock_market)

    agent = LLMAgent("gemini-flash", "google/gemini-2.0-flash-001", provider="openrouter")
    print(f"Calling {agent.agent_id} via OpenRouter...")

    signal = agent.trade(replay_state.context)
    print(f"\n=== TradingSignal ===")
    print(f"  direction:            {signal.direction}")
    print(f"  estimated_prob:       {signal.estimated_probability:.2%}")
    print(f"  confidence:           {signal.confidence:.2%}")
    print(f"  entry:                {signal.entry_condition.trigger}")
    print(f"  exit:                 {signal.exit_condition.trigger}")
    print(f"  rationale:            {signal.rationale}")

    position = simulate_position(signal, replay_state)
    print(f"\n=== SimulatedPosition ===")
    print(f"  exit_reason:          {position.exit_reason}")
    print(f"  pnl:                  {position.pnl}")
    print(f"  resolution_pnl:       {position.resolution_pnl}")

    result = evaluate_agent(signal, position, replay_state)
    print(f"\n=== AgentEvalResult ===")
    print(f"  brier_score:          {result.brier_score}")
    print(f"  edge_vs_market:       {result.edge_vs_market}")
    print(f"  directional_correct:  {result.directional_correct}")
    print(f"  simulated_pnl:        {result.simulated_pnl}")
    print(f"  resolution_pnl:       {result.resolution_pnl}")

    print("\nAll good — OpenRouter + full pipeline working.")
