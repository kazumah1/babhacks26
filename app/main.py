"""
main.py — entrypoint for a single evaluation run.

Runs one refresh cycle (fetches live prices, asks all agents to enter/exit),
then writes data/positions.json and data/results.json.

For continuous live updates, just run the dashboard — it auto-refreshes
every 5 minutes by calling run_refresh() internally.
"""

import json
from pathlib import Path
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

from pipeline import build_context
from engine import run_evaluation, AGENTS
from engine.position_ledger import load_positions, save_positions
from app.refresh import run_refresh
from app.refresh import MARKET_SLUGS

# Agents reason from the current market price
LOOKBACK_DAYS = 0


def _build_results_from_positions() -> list[dict]:
    """Convert positions.json into the results.json format for the dashboard."""
    from pipeline import CONTEXT_CACHE_DIR, _load_context_cache
    positions = load_positions()
    rows = []
    for agent_id, markets in positions.items():
        for slug, pos in markets.items():
            context_path = CONTEXT_CACHE_DIR / f"{slug}_context.json"
            if not context_path.exists():
                continue
            ctx = _load_context_cache(context_path)
            rows.append({
                "agent_id": agent_id,
                "market_id": slug,
                "market_question": ctx.market_question,
                "market_type": ctx.market_type,
                "brier_score": None,
                "edge_vs_market": 0.0,
                "directional_correct": None,
                "simulated_pnl": pos["pnl_dollars"] / max(pos["allocation"], 1)
                    if pos["allocation"] else 0.0,
                "resolution_pnl": 0.0,
                "exit_reason": pos["exit_reason"] or "open",
                "estimated_probability": pos.get("current_price", 0.0),
                "market_probability": pos.get("current_price", 0.0),
                "final_resolution": None,
                "rationale": f"Position {pos['status']}. Entry: {pos.get('entry_price', '—')}. Current: {pos.get('current_price', '—')}.",
                "confidence": 0.5,
                "direction": pos["direction"],
                "allocation": pos["allocation"],
            })
    return rows


def main():
    Path("data").mkdir(exist_ok=True)

    # Run one full refresh cycle (fetches live prices, agents enter/exit)
    run_refresh()

    # Write results.json for dashboard compatibility
    rows = _build_results_from_positions()
    with open("data/results.json", "w") as f:
        json.dump(rows, f, indent=2, default=str)
    print(f"\nResults written to data/results.json ({len(rows)} rows)")
    print("Run: streamlit run app/dashboard.py")


if __name__ == "__main__":
    main()
